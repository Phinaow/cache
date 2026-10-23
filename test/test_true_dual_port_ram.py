"""Check the cache RAM wrapper's actual CPU/memory port mapping."""
import random

import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def cpu_memory_mapping_and_byte_strobes(dut):
    dut.clka.value = 0
    dut.clkb.value = 0
    dut.ena.value = 0
    dut.enb.value = 0
    dut.wea.value = 0
    dut.web.value = 0
    dut.addra.value = 0
    dut.addrb.value = 0
    dut.dina.value = 0
    dut.dinb.value = 0
    rng = random.Random(99)
    words = [rng.getrandbits(32) for _ in range(2048)]
    for address, word in enumerate(words):
        dut.enb.value = 1
        dut.web.value = 15
        dut.addrb.value = address
        dut.dinb.value = word
        await Timer(3, unit="ns")
        dut.clkb.value = 1
        await Timer(3, unit="ns")
        dut.clkb.value = 0
    dut.enb.value = 0
    dut.web.value = 0
    for address in range(512):
        dut.ena.value = 1
        dut.addra.value = address
        await Timer(5, unit="ns")
        dut.clka.value = 1
        await Timer(5, unit="ns")
        expected = sum(words[address * 4 + index] << (32 * index) for index in range(4))
        assert int(dut.douta.value) == expected
        dut.clka.value = 0
    # Change one byte in every wide-port byte lane, then verify all CPU words.
    for byte in range(16):
        dut.addra.value = 511
        dut.dina.value = 0xAA << (8 * byte)
        dut.wea.value = 1 << byte
        await Timer(5, unit="ns")
        dut.clka.value = 1
        await Timer(5, unit="ns")
        dut.clka.value = 0
    dut.ena.value = 0
    dut.wea.value = 0
    for address in range(2044, 2048):
        dut.enb.value = 1
        dut.addrb.value = address
        await Timer(3, unit="ns")
        dut.clkb.value = 1
        await Timer(3, unit="ns")
        dut.clkb.value = 0
        assert int(dut.doutb.value) == 0xAAAAAAAA


def test_true_dual_port_ram(runner):
    runner.test(hdl_toplevel="true_dual_port_ram", test_module=__name__, test_args=["--trace"])
