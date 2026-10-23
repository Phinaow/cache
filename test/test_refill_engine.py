"""Refill: exact beat counts, RAM writes, backpressure, errors and LAST faults."""
import random

import cocotb
from cocotb.triggers import Timer


class RefillBench:
    def __init__(self, dut):
        self.dut = dut
        self.depth = 1 << len(dut.ram_addr_o)
        self.width = len(dut.axi_rdata_i)
        self.memory = [None] * self.depth

    async def cycle(self):
        dut = self.dut
        dut.clk_i.value = 0
        await Timer(5, unit="ns")
        sample = {
            "arvalid": int(dut.axi_arvalid_o.value),
            "arready": int(dut.axi_arready_i.value),
            "address": int(dut.axi_araddr_o.value),
            "length": int(dut.axi_arlen_o.value),
            "size": int(dut.axi_arsize_o.value),
            "burst": int(dut.axi_arburst_o.value),
            "rready": int(dut.axi_rready_o.value),
            "done": int(dut.addr_ready_o.value),
            "status": int(dut.status_o.value),
        }
        if dut.ram_we_o.value:
            assert dut.axi_rvalid_i.value and dut.axi_rready_o.value
            assert int(dut.ram_we_o.value) == (1 << (self.width // 8)) - 1
            address = int(dut.ram_addr_o.value)
            self.memory[address] = int(dut.ram_data_o.value)
        dut.clk_i.value = 1
        await Timer(5, unit="ns")
        return sample

    async def reset(self):
        dut = self.dut
        dut.rst_ni.value = 0
        dut.addr_valid_i.value = 0
        dut.data_i.value = 0
        dut.axi_arready_i.value = 0
        dut.axi_rvalid_i.value = 0
        dut.axi_rdata_i.value = 0
        dut.axi_rlast_i.value = 0
        dut.axi_rresp_i.value = 0
        for _ in range(3):
            await self.cycle()
        dut.rst_ni.value = 1
        await self.cycle()

    async def refill(self, base, beats, *, error_at=None, last_at=None, seed=0):
        dut = self.dut
        rng = random.Random(seed)
        words = [rng.getrandbits(self.width) for _ in range(beats + 3)]
        self.memory = [None] * self.depth
        dut["data_i.mem_addr"].value = 0x2000
        dut["data_i.nb_transfer"].value = beats - 1
        dut["data_i.cache_addr"].value = base
        dut["data_i.wb_rf"].value = 0
        dut.addr_valid_i.value = 1
        last_at = beats - 1 if last_at is None else last_at
        sent = 0
        accepted_ar = False
        previous_ar = None
        for cycle in range(200 + beats * 10):
            dut.axi_arready_i.value = int(cycle > 5)
            valid = accepted_ar and rng.randrange(4) != 0
            dut.axi_rvalid_i.value = int(valid)
            dut.axi_rdata_i.value = words[sent]
            dut.axi_rlast_i.value = int(sent == last_at)
            dut.axi_rresp_i.value = 2 if sent == error_at else 0
            sample = await self.cycle()
            command = (sample["address"], sample["length"], sample["size"], sample["burst"])
            if previous_ar is not None:
                assert sample["arvalid"] and command == previous_ar
            previous_ar = command if sample["arvalid"] and not sample["arready"] else None
            if sample["arvalid"] and sample["arready"]:
                assert not accepted_ar
                assert command == (0x2000, beats - 1, (self.width // 8).bit_length() - 1, 1)
                accepted_ar = True
            if valid and sample["rready"]:
                sent += 1
            if sample["done"]:
                assert sent == last_at + 1
                expected_status = 2 if error_at is not None or last_at != beats - 1 else 0
                assert sample["status"] == expected_status
                break
        else:
            raise AssertionError(f"Refill timeout: beats={beats}, sent={sent}")
        for address, data in enumerate(self.memory):
            index = address - base
            written = 0 <= index < min(beats, last_at + 1) and index != error_at
            assert data == (words[index] if written else None), f"Unexpected write at RAM {address}"
        dut.addr_valid_i.value = 0
        dut.axi_rvalid_i.value = 0
        for _ in range(3):
            sample = await self.cycle()
            assert not sample["done"] and not sample["arvalid"]


@cocotb.test()
async def burst_lengths_and_ram_bounds(dut):
    bench = RefillBench(dut)
    await bench.reset()
    for beats in (1, 2, 16, 64, 256):
        await bench.refill(bench.depth - beats, beats, seed=beats)


@cocotb.test()
async def memory_errors_and_malformed_last(dut):
    bench = RefillBench(dut)
    await bench.reset()
    for error_at in (0, 7, 15):
        await bench.refill(23, 16, error_at=error_at, seed=error_at)
    await bench.refill(23, 16, last_at=4)
    await bench.refill(23, 16, last_at=18)
    await bench.refill(23, 16)


@cocotb.test()
async def reset_aborts_partial_refill(dut):
    bench = RefillBench(dut)
    await bench.reset()
    dut["data_i.nb_transfer"].value = 15
    dut.addr_valid_i.value = 1
    dut.axi_arready_i.value = 1
    for _ in range(5):
        await bench.cycle()
    dut.axi_rvalid_i.value = 1
    for _ in range(4):
        await bench.cycle()
    await bench.reset()
    await bench.refill(0, 16)


def test_refill_engine(runner):
    runner.test(hdl_toplevel="refill_engine", test_module=__name__, test_args=["--trace"])
