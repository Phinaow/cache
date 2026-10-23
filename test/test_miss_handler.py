"""Miss handler: command capture, synchronous RAM, errors and held responses."""
import random

import cocotb
from cocotb.triggers import Timer

from axi_memory import AxiMemory


class MissBench:
    def __init__(self, dut):
        self.dut = dut
        self.bus = AxiMemory(dut, seed=42)
        self.depth = 1 << len(dut.ram_addr_o)
        self.width = len(dut.ram_data_i) // 8
        rng = random.Random(2026)
        self.ram = [rng.getrandbits(self.width * 8) for _ in range(self.depth)]

    async def cycle(self):
        dut = self.dut
        dut.clk_i.value = 0
        self.bus.drive()
        await Timer(5, unit="ns")
        accepted = bool(dut.cdc_valid_i.value and dut.cdc_ready_o.value)
        response = (int(dut["resp_data_o.wb_rf"].value), int(dut["resp_data_o.status"].value))
        valid = bool(dut.resp_valid_o.value)
        address = int(dut.ram_addr_o.value)
        old_data = self.ram[address]
        if dut.ram_we_o.value:
            assert int(dut.ram_we_o.value) == (1 << self.width) - 1
            self.ram[address] = int(dut.ram_data_o.value)
        self.bus.observe()
        dut.clk_i.value = 1
        await Timer(1, unit="ps")
        dut.ram_data_i.value = old_data
        await Timer(4999, unit="ps")
        return accepted, valid, response

    async def reset(self):
        dut = self.dut
        dut.rst_ni.value = 0
        dut.cdc_data_i.value = 0
        dut.cdc_valid_i.value = 0
        dut.resp_ready_i.value = 0
        dut.ram_data_i.value = 0
        for _ in range(3):
            await self.cycle()
        dut.rst_ni.value = 1
        await self.cycle()

    async def transfer(self, operation, base, beats, address, expected_status=0):
        dut = self.dut
        before_ram = self.ram.copy()
        expected_read = [self.bus.load(address + i * self.width, self.width) for i in range(beats)]
        dut["cdc_data_i.mem_addr"].value = address
        dut["cdc_data_i.nb_transfer"].value = beats - 1
        dut["cdc_data_i.cache_addr"].value = base
        dut["cdc_data_i.wb_rf"].value = operation
        dut.cdc_valid_i.value = 1
        for _ in range(20):
            accepted, _, _ = await self.cycle()
            if accepted:
                break
        else:
            raise AssertionError("Command was not accepted")
        # The caller may immediately change all command fields after acceptance.
        dut.cdc_valid_i.value = 0
        dut.cdc_data_i.value = 0
        for _ in range(100 + beats * 20):
            assert not dut.cdc_ready_o.value, "Second command accepted before completion"
            _, valid, response = await self.cycle()
            if valid:
                assert response == (operation, expected_status)
                break
        else:
            raise AssertionError("Miss handler did not respond")
        for _ in range(7):
            _, valid, held = await self.cycle()
            assert valid and held == response, "Response changed while stalled"
        dut.resp_ready_i.value = 1
        await self.cycle()
        dut.resp_ready_i.value = 0
        for _ in range(4):
            _, valid, _ = await self.cycle()
            assert not valid, "Duplicate response"
        assert dut.cdc_ready_o.value
        if operation == 1:
            assert self.ram == before_ram, "Writeback modified the cache RAM"
            actual = [self.bus.load(address + i * self.width, self.width) for i in range(beats)]
            assert actual == before_ram[base:base + beats]
        elif expected_status == 0:
            assert self.ram[base:base + beats] == expected_read
            assert self.ram[:base] == before_ram[:base]
            assert self.ram[base + beats:] == before_ram[base + beats:]


@cocotb.test()
async def mixed_commands_and_error_status(dut):
    bench = MissBench(dut)
    await bench.reset()
    for operation in (0, 0, 1, 1, 0, 1):
        for beats in (1, 2, 64, 256):
            await bench.transfer(operation, bench.depth - beats, beats, 0x4000)
    for operation, error in ((0, "next_read_error"), (1, "next_write_error"),
                             (0, "next_bad_rid"), (1, "next_bad_bid")):
        setattr(bench.bus, error, True)
        await bench.transfer(operation, 13, 16, 0x2000, expected_status=2)
        await bench.transfer(operation, 13, 16, 0x2000)


def test_miss_handler(runner):
    runner.test(hdl_toplevel="miss_handler", test_module=__name__, test_args=["--trace"])
