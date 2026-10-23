"""RAM tests: byte-level reference model, independent clocks and READ_FIRST.

Operations are serialized to avoid undefined cross-port collisions.
No power-up value is assumed.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, ReadOnly


class RamBench:
    def __init__(self, dut):
        self.dut = dut
        self.width = {p: len(getattr(dut, f"strb_{p}")) for p in ("a", "b")}
        self.depth = {p: 1 << len(getattr(dut, f"addr_{p}")) for p in ("a", "b")}
        size = self.width["a"] * self.depth["a"]
        assert size == self.width["b"] * self.depth["b"]
        self.shadow = bytearray(size)

    async def access(self, port, address, data=0, strobe=0, enable=True):
        dut = self.dut
        clock = getattr(dut, f"clk_{port}")
        width = self.width[port]
        offset = address * width
        before = int.from_bytes(self.shadow[offset:offset + width], "little")
        await FallingEdge(clock)
        getattr(dut, f"en_{port}").value = int(enable)
        getattr(dut, f"addr_{port}").value = address
        getattr(dut, f"wdata_{port}").value = data
        getattr(dut, f"strb_{port}").value = strobe
        await RisingEdge(clock)
        await ReadOnly()
        observed = int(getattr(dut, f"rdata_{port}").value)
        if enable:
            assert observed == before, f"READ_FIRST port={port} address={address}: {observed:#x} != {before:#x}"
            for byte in range(width):
                if strobe & (1 << byte):
                    self.shadow[offset + byte] = (data >> (8 * byte)) & 255
        await FallingEdge(clock)
        getattr(dut, f"en_{port}").value = 0
        getattr(dut, f"strb_{port}").value = 0
        return observed

    async def initialize(self):
        dut = self.dut
        for port in ("a", "b"):
            for signal in ("en", "strb", "addr", "wdata"):
                getattr(dut, f"{signal}_{port}").value = 0
        cocotb.start_soon(Clock(dut.clk_a, 20, unit="ns").start())
        cocotb.start_soon(Clock(dut.clk_b, 7, unit="ns").start())
        # Outputs are unknown before initialization; do not check them yet.
        for address in range(self.depth["a"]):
            await FallingEdge(dut.clk_a)
            dut.en_a.value = 1
            dut.strb_a.value = (1 << self.width["a"]) - 1
            dut.addr_a.value = address
            dut.wdata_a.value = 0
            await RisingEdge(dut.clk_a)
        await FallingEdge(dut.clk_a)
        dut.en_a.value = 0
        dut.strb_a.value = 0


@cocotb.test()
async def cross_port_masks_and_read_first(dut):
    # Initialize the reference memory and use a reproducible random seed.
    bench = RamBench(dut)
    await bench.initialize()
    rng = random.Random(0xB10C)

    # Write the entire memory, then read it through the other port.
    for writer, reader in (("a", "b"), ("b", "a")):
        width = bench.width[writer]
        for address in range(bench.depth[writer]):
            await bench.access(writer, address, rng.getrandbits(width * 8), (1 << width) - 1)
        for address in range(bench.depth[reader]):
            await bench.access(reader, address)

    # Cover every CPU mask, individual wide-port bytes and random masks.
    for port in ("a", "b"):
        width = bench.width[port]
        if width <= 4:
            masks = list(range(1 << width))
        else:
            masks = [0, (1 << width) - 1]
            masks += [1 << byte for byte in range(width)]
        masks += [rng.getrandbits(width) for _ in range(100)]
        for mask in masks:
            address = rng.randrange(bench.depth[port])
            await bench.access(port, address, rng.getrandbits(width * 8), mask)
            other = "b" if port == "a" else "a"
            first = address * width // bench.width[other]
            last = (address * width + width - 1) // bench.width[other]
            for cross_address in range(first, last + 1):
                await bench.access(other, cross_address)

    # A disabled port must preserve both memory and its output.
    for port in ("a", "b"):
        old_output = await bench.access(port, 0)
        observed = await bench.access(port, bench.depth[port] - 1,
                                   (1 << (8 * bench.width[port])) - 1,
                                   (1 << bench.width[port]) - 1, enable=False)
        assert observed == old_output
        await bench.access(port, bench.depth[port] - 1)


def test_bl_mem(runner):
    runner.test(hdl_toplevel="bl_mem", test_module=__name__, test_args=["--trace"])
