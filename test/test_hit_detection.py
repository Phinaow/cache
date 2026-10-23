"""Tags and replacement: allocation, dirty ownership and error preservation."""
import cocotb
from cocotb.triggers import Timer


class TagBench:
    def __init__(self, dut):
        self.dut = dut
        self.commands = []
        self.events = []

    async def cycle(self):
        dut = self.dut
        dut.clk_i.value = 0
        await Timer(5, unit="ns")
        hit = bool(dut.hit_o.value)
        way = int(dut.hit_addr_o.value)
        status = int(dut.lookup_status_o.value)
        if dut.access_valid_o.value:
            self.events.append(int(dut.access_data_o.value))
        command = None
        if dut.cdc_req_valid_o.value:
            command = tuple(int(dut[f"cdc_req_data_o.{field}"].value)
                            for field in ("wb_rf", "mem_addr", "cache_addr", "nb_transfer"))
        dut.clk_i.value = 1
        await Timer(5, unit="ns")
        return hit, way, status, command

    async def reset(self):
        dut = self.dut
        for name in ("awvalid_i", "awaddr_i", "arvalid_i", "araddr_i", "access_done_i",
                     "write_commit_i", "commit_way_i", "cdc_req_ready_i", "cdc_resp_valid_i"):
            getattr(dut, name).value = 0
        dut.cdc_resp_data_i.value = 0
        dut.access_ready_i.value = 1
        dut.lru_way_valid_i.value = 1
        dut.lru_way_data_i.value = 0
        dut.rst_ni.value = 0
        for _ in range(3):
            await self.cycle()
        dut.rst_ni.value = 1
        await self.cycle()

    async def access(self, tag, write=False, error_operation=None):
        dut = self.dut
        dut.awvalid_i.value = int(write)
        dut.arvalid_i.value = int(not write)
        dut.awaddr_i.value = tag
        dut.araddr_i.value = tag
        pending = None
        delay = 0
        held_command = None
        for cycle in range(100):
            dut.cdc_req_ready_i.value = int(cycle % 5 == 0 and pending is None)
            dut.cdc_resp_valid_i.value = int(pending is not None and delay == 0)
            if pending is not None:
                dut["cdc_resp_data_i.wb_rf"].value = pending[0]
                dut["cdc_resp_data_i.status"].value = 2 if pending[0] == error_operation else 0
            hit, way, status, command = await self.cycle()
            if held_command is not None:
                assert command == held_command, "Miss command changed before acceptance"
            held_command = command if command is not None and not dut.cdc_req_ready_i.value else None
            if pending is not None and delay:
                delay -= 1
            if command is not None and dut.cdc_req_ready_i.value:
                self.commands.append(command)
                pending = command
                delay = 4
                # A different PLRU output must not change the reserved victim.
                dut.lru_way_data_i.value = (int(dut.lru_way_data_i.value) + 1) % 8
            if dut.cdc_resp_valid_i.value:
                pending = None
            if hit:
                dut.awvalid_i.value = 0
                dut.arvalid_i.value = 0
                dut.cdc_resp_valid_i.value = 0
                if status == 0:
                    dut.access_done_i.value = 1
                    dut.write_commit_i.value = int(write)
                    dut.commit_way_i.value = way
                await self.cycle()
                dut.access_done_i.value = 0
                dut.write_commit_i.value = 0
                await self.cycle()
                return way, status
        raise AssertionError(f"Tag lookup timeout: tag={tag}")


@cocotb.test()
async def allocate_hit_and_replace_dirty_lines(dut):
    bench = TagBench(dut)
    await bench.reset()
    for tag in range(8):
        assert await bench.access(tag, write=True) == (tag, 0)
    assert len(bench.events) == 8
    assert [command[0] for command in bench.commands] == [0] * 8
    for _ in range(3):
        for tag in range(8):
            assert await bench.access(tag) == (tag, 0)
    assert len(bench.events) == 32, "Every hit must update PLRU, not only the first hit"
    before = len(bench.commands)
    dut.lru_way_data_i.value = 3
    assert await bench.access(40) == (3, 0)
    assert bench.commands[before:] == [(1, 3 * 1024, 3 * 64, 63), (0, 40 * 1024, 3 * 64, 63)]


@cocotb.test()
async def failed_writeback_preserves_dirty_victim_and_failed_refill_is_invalid(dut):
    bench = TagBench(dut)
    await bench.reset()
    for tag in range(8):
        await bench.access(tag, write=True)
    dut.lru_way_data_i.value = 2
    before = len(bench.commands)
    assert (await bench.access(20, error_operation=1))[1] == 2
    assert len(bench.commands) == before + 1, "Refill followed a failed writeback"
    assert await bench.access(2) == (2, 0), "The dirty victim was lost"
    dut.lru_way_data_i.value = 2
    assert (await bench.access(20, error_operation=0))[1] == 2
    before = len(bench.commands)
    assert (await bench.access(20))[1] == 0
    assert len(bench.commands) == before + 1, "Failed refill left a false hit"


def test_hit_detection(runner):
    runner.test(hdl_toplevel="hit_detection", test_module=__name__, test_args=["--trace"])
