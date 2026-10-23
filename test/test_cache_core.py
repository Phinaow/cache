"""Full cache core: real dual-port RTL RAM, both CDC paths and AXI memory."""
import random
import os

import pytest

import cocotb
from cocotb.triggers import Timer

from axi_memory import AxiMemory
from cpu_master import CpuMaster, sample_cpu


class CoreBench:
    def __init__(self, dut, cpu_half_period=5, memory_half_period=3):
        self.dut = dut
        self.bus = AxiMemory(dut, seed=2026)
        self.cpu = CpuMaster(dut, self.cycle)
        self.expected = {}
        self.time = 0
        self.cpu_half_period = cpu_half_period
        self.memory_half_period = memory_half_period
        dut.clk_cpu_i.value = 0
        dut.clk_mem_i.value = 0

    async def cycle(self):
        dut = self.dut
        while True:
            self.bus.drive()
            await Timer(1, unit="ns")
            self.time += 1
            cpu_edge = self.time % self.cpu_half_period == 0
            memory_edge = self.time % self.memory_half_period == 0
            cpu_rising = cpu_edge and not int(dut.clk_cpu_i.value)
            memory_rising = memory_edge and not int(dut.clk_mem_i.value)
            sample = sample_cpu(dut) if cpu_rising else None
            if memory_rising and int(dut.rst_ni.value):
                self.bus.observe()
            if cpu_edge:
                dut.clk_cpu_i.value = 1 - int(dut.clk_cpu_i.value)
            if memory_edge:
                dut.clk_mem_i.value = 1 - int(dut.clk_mem_i.value)
            await Timer(1, unit="ps")
            if cpu_rising:
                return sample

    async def reset(self):
        self.cpu.initialize()
        self.bus.reset_protocol()
        self.dut.rst_ni.value = 0
        for _ in range(5):
            await self.cycle()
        self.dut.rst_ni.value = 1
        for _ in range(8):
            await self.cycle()

    def expected_word(self, address):
        return int.from_bytes(bytes(self.expected.get(address + i, (13 * (address + i) + 7) & 255)
                                    for i in range(4)), "little")

    async def write(self, address, data, mask=15, **kwargs):
        await self.cpu.write(address, data, mask, **kwargs)
        if kwargs.get("status", 0) == 0:
            for byte in range(4):
                if mask & (1 << byte):
                    self.expected[address + byte] = (data >> (8 * byte)) & 255

    async def read(self, address):
        observed = await self.cpu.read(address)
        assert observed == self.expected_word(address), f"CPU read mismatch at {address:#x}: {observed:#x}"


@cocotb.test()
async def dirty_lines_survive_eviction_and_clock_crossings(dut):
    bench = CoreBench(dut)
    await bench.reset()
    rng = random.Random(0xCA5E)
    addresses = []
    for tag in range(18):
        for word in (0, 1, 15, 255):
            address = tag * 1024 + word * 4
            addresses.append(address)
            await bench.write(address, rng.getrandbits(32), 1 + rng.randrange(15),
                              aw_delay=rng.randrange(4), w_delay=rng.randrange(4))
            await bench.read(address)
    rng.shuffle(addresses)
    for address in addresses:
        await bench.read(address)
    assert any(event[0] == "aw" for event in bench.bus.events)


@cocotb.test()
async def error_status_crosses_back_to_the_cpu(dut):
    bench = CoreBench(dut, cpu_half_period=3, memory_half_period=7)
    await bench.reset()
    ways = int(os.environ.get("TEST_CACHE_LINES", "8"))
    for tag in range(ways):
        await bench.write(tag * 1024, 0x12340000 + tag)
    before = len(bench.bus.events)
    for invalid_address in (0x20000000, 0x80000000):
        await bench.cpu.write(invalid_address, 0xDEADBEEF, status=2)
        await bench.cpu.read(invalid_address, status=2)
    assert len(bench.bus.events) == before, "Illegal aliases reached external memory"
    await bench.read(0)
    bench.bus.next_write_error = True
    await bench.cpu.read(20 * 1024, status=2)
    for tag in range(ways):
        await bench.read(tag * 1024)

    bench.bus.next_read_error = True
    await bench.cpu.read(20 * 1024, status=2)
    await bench.read(20 * 1024)
    for tag in range(ways):
        await bench.read(tag * 1024)


@cocotb.test()
async def last_legal_word_is_not_rejected_or_aliased(dut):
    bench = CoreBench(dut)
    await bench.reset()
    await bench.write(0, 0x11223344)
    await bench.write(0x1FFFFFFC, 0xAABBCCDD)
    await bench.read(0x1FFFFFFC)
    await bench.read(0)
    assert any(event[1] >= 0x1FFFF000 for event in bench.bus.events)


@cocotb.test()
async def global_reset_cancels_each_memory_phase(dut):
    bench = CoreBench(dut)
    ways = int(os.environ.get("TEST_CACHE_LINES", "8"))
    for pause in ("pause_ar", "pause_r", "pause_aw", "pause_w", "pause_b"):
        await bench.reset()
        if pause in ("pause_aw", "pause_w", "pause_b"):
            for tag in range(ways):
                await bench.write(tag * 1024, 0xBEEF0000 + tag)
        setattr(bench.bus, pause, True)
        dut.axi_araddr_i.value = 0x7000
        dut.axi_arvalid_i.value = 1
        for _ in range(3000):
            sample = await bench.cycle()
            if sample.arready:
                dut.axi_arvalid_i.value = 0
            reached = {
                "pause_ar": bool(dut.m_axi_arvalid.value),
                "pause_r": bench.bus.read is not None,
                "pause_aw": bool(dut.m_axi_awvalid.value),
                "pause_w": bool(dut.m_axi_wvalid.value),
                "pause_b": bench.bus.write_response is not None and bool(dut.m_axi_bready.value),
            }
            if reached[pause]:
                break
        else:
            raise AssertionError(f"Memory phase not reached: {pause}")
        await bench.reset()
        for address in (0, 0x7000):
            expected = bench.bus.load(address, 4)
            assert await bench.cpu.read(address) == expected


@pytest.mark.parametrize("runner", [
    {},
    {"CACHE_LINES": 1, "CACHE_CPU_WORDS": 256},
    {"CACHE_LINES": 2, "CACHE_CPU_WORDS": 128},
    {"CACHE_LINES": 4, "CACHE_CPU_WORDS": 256},
], indirect=True)
def test_cache_core(runner):
    runner.test(hdl_toplevel="cache_core", test_module=__name__, test_args=["--trace"],
                extra_env={"TEST_CACHE_LINES": str(runner.defines.get("CACHE_LINES", 8))})
