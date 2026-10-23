"""Reset release requires two local edges; assertion needs no clock."""
import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def asynchronous_assertion_and_synchronous_release(dut):
    dut.clk_i.value = 0
    for _ in range(4):
        dut.rst_ni.value = 0
        await Timer(2, unit="ns")
        assert dut.rst_no.value == 0
        dut.rst_ni.value = 1
        await Timer(3, unit="ns")
        assert dut.rst_no.value == 0
        for edge in range(2):
            dut.clk_i.value = 1
            await Timer(2, unit="ns")
            assert int(dut.rst_no.value) == int(edge == 1)
            dut.clk_i.value = 0
            await Timer(2, unit="ns")
        # Assert reset between edges, while the clock remains stopped.
        dut.rst_ni.value = 0
        await Timer(1, unit="ns")
        assert dut.rst_no.value == 0


def test_reset_sync(runner):
    runner.test(hdl_toplevel="reset_sync", test_module=__name__, test_args=["--trace"])
