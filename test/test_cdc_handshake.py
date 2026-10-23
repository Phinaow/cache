"""Mailbox CDC: ordered delivery, backpressure and reset under unrelated clocks."""
import random

import cocotb
from cocotb.triggers import Timer


class MailboxBench:
    """Schedule both clock domains on a common simulation time grid.

    Inputs change before the edge; transfers are sampled before either clock
    rises. Coincident edges therefore cannot race against the Python drivers.
    """
    def __init__(self, dut, source_half_period, destination_half_period):
        self.dut = dut
        self.source_half_period = source_half_period
        self.destination_half_period = destination_half_period
        self.time = 0
        dut.clk_src_i.value = 0
        dut.clk_dst_i.value = 0
        dut.src_valid_i.value = 0
        dut.src_data_i.value = 0
        dut.dst_ready_i.value = 0
        dut.rst_src_ni.value = 0
        dut.rst_dst_ni.value = 0

    async def step(self):
        dut = self.dut
        await Timer(1, unit="ns")
        self.time += 1
        source_edge = self.time % self.source_half_period == 0
        destination_edge = self.time % self.destination_half_period == 0
        source_rising = source_edge and not int(dut.clk_src_i.value)
        destination_rising = destination_edge and not int(dut.clk_dst_i.value)
        sent = source_rising and int(dut.src_valid_i.value) and int(dut.src_ready_o.value)
        received = destination_rising and int(dut.dst_valid_o.value) and int(dut.dst_ready_i.value)
        data = int(dut.dst_data_o.value)
        if source_edge:
            dut.clk_src_i.value = 1 - int(dut.clk_src_i.value)
        if destination_edge:
            dut.clk_dst_i.value = 1 - int(dut.clk_dst_i.value)
        await Timer(1, unit="ps")
        return bool(sent), bool(received), data, destination_rising

    async def reset(self):
        dut = self.dut
        dut.rst_src_ni.value = 0
        dut.rst_dst_ni.value = 0
        dut.src_valid_i.value = 0
        dut.dst_ready_i.value = 0
        for _ in range(6 * max(self.source_half_period, self.destination_half_period)):
            await self.step()
        assert dut.src_ready_o.value == 0
        assert dut.dst_valid_o.value == 0
        dut.rst_src_ni.value = 1
        dut.rst_dst_ni.value = 1
        for _ in range(6 * max(self.source_half_period, self.destination_half_period)):
            await self.step()

    async def exchange(self, count, seed):
        dut = self.dut
        rng = random.Random(seed)
        words = [rng.getrandbits(len(dut.src_data_i)) for _ in range(count)]
        sent_words = []
        received_words = []
        held = None
        for tick in range(count * 1000):
            if len(sent_words) < count:
                dut.src_data_i.value = words[len(sent_words)]
                dut.src_valid_i.value = 1
            else:
                # Poison the live input while the mailbox finishes the last item.
                dut.src_data_i.value = rng.getrandbits(len(dut.src_data_i))
                dut.src_valid_i.value = 0
            dut.dst_ready_i.value = int(tick % 97 > 25 and rng.randrange(4) != 0)
            sent, received, data, destination_edge = await self.step()
            if sent:
                sent_words.append(words[len(sent_words)])
            if destination_edge:
                if held is not None:
                    assert data == held, "Destination data changed during a stall"
                if received:
                    assert len(received_words) < len(sent_words), "Phantom or duplicate item"
                    assert data == sent_words[len(received_words)]
                    received_words.append(data)
                # Check the newly visible pending word on the next sampled edge.
                held = int(dut.dst_data_o.value) if dut.dst_valid_o.value and not dut.dst_ready_i.value else None
            if len(received_words) == count:
                break
        else:
            raise AssertionError(f"CDC timeout: sent={len(sent_words)}, received={len(received_words)}, seed={seed}")
        assert received_words == words
        dut.src_valid_i.value = 0
        dut.dst_ready_i.value = 1
        for _ in range(20 * max(self.source_half_period, self.destination_half_period)):
            _, received, _, _ = await self.step()
            assert not received, "Duplicate item after the mailbox was drained"


@cocotb.test()
async def unrelated_clocks_and_backpressure(dut):
    for seed, periods in enumerate(((2, 7), (7, 2), (3, 5), (4, 4))):
        bench = MailboxBench(dut, *periods)
        await bench.reset()
        await bench.exchange(100, seed)


@cocotb.test()
async def global_reset_cancels_pending_item(dut):
    bench = MailboxBench(dut, 3, 7)
    await bench.reset()
    dut.src_valid_i.value = 1
    dut.src_data_i.value = 0xDEADBEEF
    for _ in range(200):
        await bench.step()
        if dut.dst_valid_o.value:
            break
    else:
        raise AssertionError("No pending destination word")
    await bench.reset()
    await bench.exchange(30, 2026)


def test_cdc_handshake(runner):
    runner.test(hdl_toplevel="cdc_handshake", test_module=__name__, test_args=["--trace"])
