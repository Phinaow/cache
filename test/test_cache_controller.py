"""Cache controller integration with a synchronous RAM and a memory-operation model."""
import random

import cocotb
from cocotb.triggers import Timer

from cpu_master import CpuMaster, sample_cpu


class ControllerBench:
    def __init__(self, dut):
        self.dut = dut
        self.cpu = CpuMaster(dut, self.cycle)
        self.ram = bytearray(8192)
        self.dram = {}
        self.expected = {}
        self.commands = []
        self.pending = None
        self.response = None
        self.delay = 0
        self.next_error = None

    def byte(self, address):
        return self.dram.get(address, (13 * address + 7) & 255)

    def expected_word(self, address):
        return int.from_bytes(bytes(self.expected.get(address + i, (13 * (address + i) + 7) & 255)
                                    for i in range(4)), "little")

    async def cycle(self):
        dut = self.dut
        dut.clk_i.value = 0
        if self.pending is not None:
            self.delay -= 1
            if self.delay == 0:
                operation, address, base, beats = self.pending
                error = self.next_error == operation
                if error:
                    self.next_error = None
                count = beats * 16
                if operation == 0:
                    # Failed refills overwrite part of the line before reporting.
                    for byte in range(count // 2 if error else count):
                        self.ram[base * 16 + byte] = self.byte(address + byte)
                elif not error:
                    for byte in range(count):
                        self.dram[address + byte] = self.ram[base * 16 + byte]
                self.response = (operation, 2 if error else 0)
                self.pending = None
        dut.cdc_req_ready_i.value = int(self.pending is None and self.response is None)
        dut.cdc_resp_valid_i.value = int(self.response is not None)
        dut["cdc_resp_data_i.wb_rf"].value = self.response[0] if self.response else 0
        dut["cdc_resp_data_i.status"].value = self.response[1] if self.response else 0
        await Timer(5, unit="ns")
        sample = sample_cpu(dut)
        ram_address = int(dut.ram_addr_o.value) * 4
        old_data = int.from_bytes(self.ram[ram_address:ram_address + 4], "little")
        mask = int(dut.ram_we_o.value)
        data = int(dut.ram_data_o.value)
        if mask:
            assert self.pending is None, "CPU wrote RAM during a memory transfer"
            for byte in range(4):
                if mask & (1 << byte):
                    self.ram[ram_address + byte] = (data >> (8 * byte)) & 255
        if dut.cdc_req_valid_o.value and dut.cdc_req_ready_i.value:
            self.pending = tuple(int(dut[f"cdc_req_data_o.{field}"].value)
                                 for field in ("wb_rf", "mem_addr", "cache_addr", "nb_transfer"))
            operation, address, base, length = self.pending
            self.pending = (operation, address, base, length + 1)
            self.commands.append(self.pending)
            self.delay = 5
        if dut.cdc_resp_valid_i.value and dut.cdc_resp_ready_o.value:
            self.response = None
        dut.clk_i.value = 1
        await Timer(1, unit="ps")
        dut.ram_data_i.value = old_data
        await Timer(4999, unit="ps")
        return sample

    async def reset(self):
        self.cpu.initialize()
        self.dut.rst_ni.value = 0
        self.dut.ram_data_i.value = 0
        for _ in range(3):
            await self.cycle()
        self.dut.rst_ni.value = 1
        await self.cycle()

    async def write(self, address, data, mask=15, **kwargs):
        await self.cpu.write(address, data, mask, **kwargs)
        if kwargs.get("status", 0) == 0:
            for byte in range(4):
                if mask & (1 << byte):
                    self.expected[address + byte] = (data >> (8 * byte)) & 255

    async def read(self, address):
        assert await self.cpu.read(address) == self.expected_word(address), f"CPU mismatch at {address:#x}"


@cocotb.test()
async def masks_dirty_evictions_and_reloads(dut):
    bench = ControllerBench(dut)
    await bench.reset()
    rng = random.Random(0xCAC4E)
    for tag in range(20):
        for mask in range(16):
            address = tag * 1024 + 4 * mask
            await bench.write(address, rng.getrandbits(32), mask,
                              aw_delay=mask % 3, w_delay=(mask + 1) % 3)
            await bench.read(address)
    for address in bench.expected.copy():
        if address % 4 == 0:
            await bench.read(address)
    assert any(command[0] == 1 for command in bench.commands), "No dirty eviction exercised"
    # A pure hit must not generate memory traffic.
    before = len(bench.commands)
    for _ in range(5):
        await bench.read(19 * 1024 + 60)
    assert len(bench.commands) == before


@cocotb.test()
async def failed_eviction_and_failed_refill(dut):
    bench = ControllerBench(dut)
    await bench.reset()
    for tag in range(8):
        await bench.write(tag * 1024, 0xCAFE0000 + tag)
    bench.next_error = 1
    await bench.cpu.read(20 * 1024, status=2)
    # Every dirty word must still be readable after the failed eviction.
    for tag in range(8):
        await bench.read(tag * 1024)
    bench.next_error = 0
    await bench.cpu.read(20 * 1024, status=2)
    await bench.read(20 * 1024)
    for tag in range(8):
        await bench.read(tag * 1024)


@cocotb.test()
async def invalid_addresses_and_zero_strobes_have_no_side_effects(dut):
    bench = ControllerBench(dut)
    await bench.reset()
    for address in (1, 2, 3, 0x20000000, 0x80000000, 0xFFFFFFFF):
        await bench.cpu.write(address, 0xDEADBEEF, status=2)
        await bench.cpu.read(address, status=2)
    await bench.write(0, 0xDEADBEEF, mask=0)
    assert not bench.commands
    assert bench.ram == bytearray(8192)
    await bench.read(0)


def test_cache_controller(runner):
    runner.test(hdl_toplevel="cache_controller", test_module=__name__, test_args=["--trace"])
