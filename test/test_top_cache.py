"""Physical top wiring and reset/calibration sequencing with a functional MIG model.

This validates the cache integration, not DDR3 electrical behavior or timing.
"""
import random

import cocotb
from cocotb.triggers import Timer

from cpu_master import CpuMaster, sample_cpu


class TopBench:
    def __init__(self, dut):
        self.dut = dut
        self.time = 0
        self.cpu = CpuMaster(dut, self.cycle)
        dut.clk_cpu_i.value = 0
        dut.clk_mig_i.value = 0
        dut.clk_ref_i.value = 0

    async def cycle(self):
        dut = self.dut
        while True:
            await Timer(1, unit="ns")
            self.time += 1
            cpu_edge = self.time % 5 == 0
            memory_edge = self.time % 3 == 0
            cpu_rising = cpu_edge and not int(dut.clk_cpu_i.value)
            sample = sample_cpu(dut) if cpu_rising else None
            if cpu_edge:
                dut.clk_cpu_i.value = 1 - int(dut.clk_cpu_i.value)
            if memory_edge:
                dut.clk_mig_i.value = 1 - int(dut.clk_mig_i.value)
                dut.clk_ref_i.value = 1 - int(dut.clk_ref_i.value)
            await Timer(1, unit="ps")
            if cpu_rising:
                return sample


@cocotb.test()
async def calibration_blocks_requests_then_data_survives_evictions(dut):
    bench = TopBench(dut)
    bench.cpu.initialize()
    dut.rst_ni.value = 0
    for _ in range(4):
        await bench.cycle()
    dut.rst_ni.value = 1
    for _ in range(8):
        sample = await bench.cycle()
        assert not (sample.arready or sample.awready or sample.wready), "CPU ready before calibration"
    rng = random.Random(0x70F)
    words = {tag * 1024: rng.getrandbits(32) for tag in range(20)}
    for address, data in words.items():
        await bench.cpu.write(address, data)
        assert await bench.cpu.read(address) == data
    for address, data in words.items():
        assert await bench.cpu.read(address) == data
    # Calibration loss resets both core domains and blocks the CPU again.
    dut.mig_inst.test_calibration_enable.value = 0
    for _ in range(5):
        sample = await bench.cycle()
        assert not (sample.arready or sample.awready or sample.wready)
    dut.mig_inst.test_calibration_enable.value = 1
    for _ in range(12):
        await bench.cycle()
    await bench.cpu.write(0, 0xDEADBEEF)
    assert await bench.cpu.read(0) == 0xDEADBEEF


def test_top_cache(runner):
    runner.test(hdl_toplevel="top_cache", test_module=__name__, test_args=["--trace"])
