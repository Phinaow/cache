"""CPU frontend: independent channels, synchronous RAM and side-effect-free errors."""
import random

import cocotb
from cocotb.triggers import Timer

from cpu_master import CpuMaster, sample_cpu


class TransactionBench:
    def __init__(self, dut):
        self.dut = dut
        self.cpu = CpuMaster(dut, self.cycle)
        self.rng = random.Random(40)
        self.memory = [self.rng.getrandbits(32) for _ in range(1 << len(dut.ram_addr_o))]
        self.lookup_delay = 3
        self.lookup_status = 0
        self.way = 0
        self.lookup_cycles = 0
        self.lookups = 0
        self.commits = []

    async def cycle(self):
        dut = self.dut
        dut.clk_i.value = 0
        active = bool(dut.arvalid_o.value or dut.awvalid_o.value)
        if active:
            if self.lookup_cycles == 0:
                self.lookups += 1
            self.lookup_cycles += 1
        else:
            self.lookup_cycles = 0
        dut.hit_i.value = int(active and self.lookup_cycles > self.lookup_delay)
        dut.hit_addr_i.value = self.way
        dut.lookup_status_i.value = self.lookup_status
        await Timer(5, unit="ns")
        sample = sample_cpu(dut)
        address = int(dut.ram_addr_o.value)
        old_data = self.memory[address]
        mask = int(dut.ram_we_o.value)
        data = int(dut.ram_data_o.value)
        for byte in range(4):
            if mask & (1 << byte):
                bits = 255 << (8 * byte)
                self.memory[address] = (self.memory[address] & ~bits) | (data & bits)
        if dut.access_done_o.value:
            self.commits.append((int(dut.commit_way_o.value), bool(dut.write_commit_o.value)))
        dut.clk_i.value = 1
        await Timer(1, unit="ps")
        dut.ram_data_i.value = old_data
        await Timer(4999, unit="ps")
        return sample

    async def reset(self):
        self.cpu.initialize()
        self.dut.rst_ni.value = 0
        self.dut.hit_i.value = 0
        self.dut.hit_addr_i.value = 0
        self.dut.lookup_status_i.value = 0
        self.dut.ram_data_i.value = 0
        for _ in range(3):
            await self.cycle()
        self.dut.rst_ni.value = 1
        await self.cycle()


@cocotb.test()
async def independent_channels_masks_and_synchronous_reads(dut):
    bench = TransactionBench(dut)
    await bench.reset()
    for way in range(8):
        bench.way = way
        for mask in range(16):
            address = 0x4000 + 4 * mask
            ram_address = way * 256 + mask
            before = bench.memory[ram_address]
            data = bench.rng.getrandbits(32)
            await bench.cpu.write(address, data, mask, aw_delay=mask % 3, w_delay=(mask + 1) % 3)
            expected = before
            for byte in range(4):
                if mask & (1 << byte):
                    bits = 255 << (8 * byte)
                    expected = (expected & ~bits) | (data & bits)
            assert bench.memory[ram_address] == expected
            assert await bench.cpu.read(address) == expected
    assert len(bench.commits) == 8 * (15 + 16)


@cocotb.test()
async def illegal_addresses_and_lookup_errors(dut):
    bench = TransactionBench(dut)
    await bench.reset()
    before = bench.memory.copy()
    for address in (1, 2, 3, 0x20000000, 0x80000000, 0xFFFFFFFF):
        await bench.cpu.write(address, 0x12345678, status=2)
        assert await bench.cpu.read(address, status=2) == 0
    assert bench.memory == before and bench.lookups == 0 and not bench.commits
    bench.lookup_status = 2
    await bench.cpu.write(0x1000, 0xABCDEF12, status=2)
    assert await bench.cpu.read(0x1000, status=2) == 0
    assert bench.memory == before and not bench.commits
    bench.lookup_status = 0
    await bench.cpu.write(0x1000, 0xABCDEF12)
    assert await bench.cpu.read(0x1000) == 0xABCDEF12


@cocotb.test()
async def simultaneous_read_and_write_are_both_served(dut):
    bench = TransactionBench(dut)
    await bench.reset()
    dut.axi_araddr_i.value = 0x1000
    dut.axi_awaddr_i.value = 0x1004
    dut.axi_wdata_i.value = 0xDEADBEEF
    dut.axi_wstrb_i.value = 15
    dut.axi_arvalid_i.value = 1
    dut.axi_awvalid_i.value = 1
    dut.axi_wvalid_i.value = 1
    dut.axi_rready_i.value = 1
    dut.axi_bready_i.value = 1
    reads = writes = 0
    for _ in range(80):
        sample = await bench.cycle()
        if sample.arready:
            dut.axi_arvalid_i.value = 0
        if sample.awready:
            dut.axi_awvalid_i.value = 0
        if sample.wready:
            dut.axi_wvalid_i.value = 0
        reads += sample.rvalid
        writes += sample.bvalid
    assert (reads, writes) == (1, 1)
    assert bench.memory[1] == 0xDEADBEEF


def test_transaction(runner):
    runner.test(hdl_toplevel="transaction", test_module=__name__, test_args=["--trace"])
