"""Writeback tests: synchronous RAM, AXI stalls, burst limits and reset.

Layout: sampled signals, a small test bench, named scenarios, pytest entry point.
No wrapper or generated metadata is required.
"""
from dataclasses import dataclass
import random

import cocotb
from cocotb.triggers import ReadOnly, Timer


@dataclass(frozen=True)
class Sample:
    """Signals sampled before the rising edge; a transfer is VALID and READY."""
    awvalid: int
    awready: int
    awaddr: int
    awlen: int
    awsize: int
    awburst: int
    wvalid: int
    wready: int
    wdata: int
    wstrb: int
    wlast: int
    bvalid: int
    bready: int
    done: int
    status: int


class WritebackBench:
    """Drive one cycle at a time to avoid races between stimulus and sampling.

    The RAM samples its address at the rising edge and updates its output after
    that edge. The DUT sees the previous RAM output, as with synchronous BRAM.
    Each address starts with a different, reproducible data word.
    """

    def __init__(self, dut):
        self.dut = dut
        self.word_bytes = len(dut.ram_data_i) // 8
        self.depth = 1 << len(dut.ram_addr_o)
        rng = random.Random(0xCAFE)
        self.memory = [rng.getrandbits(self.word_bytes * 8) for _ in range(self.depth)]

    async def tick(self):
        dut = self.dut
        await Timer(5, unit="ns")
        await ReadOnly()
        ram_address = int(dut.ram_addr_o.value)
        sample = Sample(
            awvalid=int(dut.axi_awvalid_o.value),
            awready=int(dut.axi_awready_i.value),
            awaddr=int(dut.axi_awaddr_o.value),
            awlen=int(dut.axi_awlen_o.value),
            awsize=int(dut.axi_awsize_o.value),
            awburst=int(dut.axi_awburst_o.value),
            wvalid=int(dut.axi_wvalid_o.value),
            wready=int(dut.axi_wready_i.value),
            wdata=int(dut.axi_wdata_o.value),
            wstrb=int(dut.axi_wstrb_o.value),
            wlast=int(dut.axi_wlast_o.value),
            bvalid=int(dut.axi_bvalid_i.value),
            bready=int(dut.axi_bready_o.value),
            done=int(dut.addr_ready_o.value),
            status=int(dut.status_o.value),
        )
        await Timer(1, unit="ps")  # Leave ReadOnly before driving signals.
        dut.clk_i.value = 1
        await Timer(1, unit="ps")  # Update the RAM output after the edge.
        dut.ram_data_i.value = self.memory[ram_address]
        await Timer(4998, unit="ps")
        dut.clk_i.value = 0
        return sample

    async def reset(self):
        dut = self.dut
        dut.clk_i.value = 0
        dut.rst_ni.value = 0
        dut.addr_valid_i.value = 0
        dut["data_i.mem_addr"].value = 0
        dut["data_i.nb_transfer"].value = 0
        dut["data_i.cache_addr"].value = 0
        dut["data_i.wb_rf"].value = 1
        dut.ram_data_i.value = 0
        dut.axi_awready_i.value = 0
        dut.axi_wready_i.value = 0
        dut.axi_bvalid_i.value = 0
        dut.axi_bresp_i.value = 0
        for _ in range(3):
            sample = await self.tick()
            assert not (sample.awvalid or sample.wvalid or sample.bready or sample.done), "Outputs active during reset"
        dut.rst_ni.value = 1
        await self.tick()

    def command(self, base, beats, address):
        dut = self.dut
        assert 1 <= beats <= 256 and base + beats <= self.depth
        assert address % self.word_bytes == 0
        dut["data_i.mem_addr"].value = address
        dut["data_i.nb_transfer"].value = beats - 1
        dut["data_i.cache_addr"].value = base
        dut["data_i.wb_rf"].value = 1
        dut.addr_valid_i.value = 1

    async def burst(self, base, beats, address, *, stalls=False, seed=0, response=0):
        """Check every beat, including payload stability while stalled.

        Hold READY low until VALID appears on the first, middle and last beats.
        This also catches a producer that incorrectly waits for READY.
        """
        dut = self.dut
        rng = random.Random(seed)
        self.command(base, beats, address)
        dut.axi_bresp_i.value = response
        accepted_aw = 0
        received = []
        held_aw = held_w = None
        forced_stalls = {i: 0 for i in (0, beats // 2, beats - 1)}
        response_delay = 0
        stalled_last = 0

        for cycle in range(100 + beats * 30):
            dut.axi_awready_i.value = int(cycle >= (5 if stalls else 0))
            beat = len(received)
            if stalls and beat in forced_stalls and forced_stalls[beat] < 4:
                ready = 0
            else:
                ready = int(not stalls or rng.randrange(4) != 0)
            dut.axi_wready_i.value = ready
            if beat == beats:
                response_delay += 1
            dut.axi_bvalid_i.value = int(beat == beats and response_delay > (7 if stalls else 0))
            sample = await self.tick()

            # VALID and the entire payload must remain stable until transfer.
            aw_payload = (sample.awaddr, sample.awlen, sample.awsize, sample.awburst)
            w_payload = (sample.wdata, sample.wstrb, sample.wlast)
            if held_aw is not None:
                assert sample.awvalid and aw_payload == held_aw, "AW changed before handshake"
            if held_w is not None:
                assert sample.wvalid and w_payload == held_w, "W payload/VALID changed under stall"
            held_aw = aw_payload if sample.awvalid and not sample.awready else None
            held_w = w_payload if sample.wvalid and not sample.wready else None

            if sample.awvalid and sample.awready:
                accepted_aw += 1
                assert accepted_aw == 1, "Duplicate AW"
                assert aw_payload == (address, beats - 1, self.word_bytes.bit_length() - 1, 1)
            if sample.wvalid:
                assert accepted_aw == 1, "W before AW in this serialized engine"
                assert len(received) < beats, "Extra W beat"
                expected = (self.memory[base + len(received)], (1 << self.word_bytes) - 1,
                            int(len(received) == beats - 1))
                assert w_payload == expected, f"beat {len(received)}/{beats}: {w_payload} != {expected}"
                if not sample.wready and len(received) in forced_stalls:
                    forced_stalls[len(received)] += 1
                    if len(received) == beats - 1:
                        stalled_last += 1
                if sample.wready:
                    received.append(sample.wdata)
            if sample.bready:
                assert len(received) == beats, "BREADY before all data was transferred"
            if sample.done:
                assert sample.bvalid and sample.bready, "Completion before B handshake"
                assert sample.status == (0 if response == 0 else 2)
                assert received == self.memory[base:base + beats]
                if stalls:
                    assert stalled_last >= 4, "Last-beat stall was not exercised"
                break
        else:
            raise AssertionError(f"Timeout: base={base}, beats={beats}, received={len(received)}, seed={seed}")

        # Complete once, then return to idle without repeating the command.
        dut.addr_valid_i.value = 0
        dut.axi_bvalid_i.value = 0
        for _ in range(3):
            sample = await self.tick()
            assert not (sample.awvalid or sample.wvalid or sample.bready or sample.done), "Operation repeated after completion"


@cocotb.test()
async def lengths_and_boundaries(dut):
    """Check every beat at both ends of RAM, for short and maximum bursts."""
    bench = WritebackBench(dut)
    await bench.reset()
    for beats in (1, 2, 16, 64, 256):
        await bench.burst(0, beats, 0)
        await bench.burst(bench.depth - beats, beats, 0x1000)


@cocotb.test()
async def backpressure_and_delayed_response(dut):
    bench = WritebackBench(dut)
    await bench.reset()
    for seed, beats in enumerate((1, 2, 17, 64, 256)):
        dut._log.info("Backpressure seed=%d beats=%d", seed, beats)
        await bench.burst(13, beats, 0x2400, stalls=True, seed=seed)


@cocotb.test()
async def randomized_bursts(dut):
    bench = WritebackBench(dut)
    await bench.reset()
    rng = random.Random(0xBACC)
    for case in range(25):
        beats = rng.randint(1, 256)
        base = rng.randint(0, bench.depth - beats)
        await bench.burst(base, beats, 0x4000, stalls=True, seed=case + 100)


@cocotb.test()
async def reset_during_each_phase(dut):
    """Reset in each phase, then verify that a fresh command completes."""
    bench = WritebackBench(dut)
    for phase in ("idle", "aw", "w", "last", "b"):
        await bench.reset()
        if phase != "idle":
            bench.command(7, 4, 0x1000)
            transferred = 0
            for _ in range(80):
                dut.axi_awready_i.value = int(phase != "aw")
                dut.axi_wready_i.value = int(phase == "b" or (phase == "last" and transferred < 3))
                sample = await bench.tick()
                if sample.wvalid and sample.wready:
                    transferred += 1
                if ((phase == "aw" and sample.awvalid)
                        or (phase == "w" and sample.wvalid)
                        or (phase == "last" and sample.wvalid and sample.wlast and not sample.wready)
                        or (phase == "b" and sample.bready)):
                    break
            else:
                raise AssertionError(f"Phase not reached: {phase}")
        await bench.reset()
        await bench.burst(19, 3, 0x2000, stalls=True, seed=42)


@cocotb.test()
async def ignore_refill_requests(dut):
    bench = WritebackBench(dut)
    await bench.reset()
    bench.command(0, 1, 0)
    dut["data_i.wb_rf"].value = 0
    for _ in range(12):
        sample = await bench.tick()
        assert not (sample.awvalid or sample.wvalid or sample.bready or sample.done)
    dut.addr_valid_i.value = 0
    await bench.burst(0, 1, 0)


@cocotb.test()
async def memory_response_errors(dut):
    bench = WritebackBench(dut)
    await bench.reset()
    for response in (2, 3, 0):
        await bench.burst(13, 16, 0x3000, stalls=True, seed=response, response=response)


def test_writeback_engine(runner):
    runner.test(hdl_toplevel="writeback_engine", test_module=__name__, test_args=["--trace"])
