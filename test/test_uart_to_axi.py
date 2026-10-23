"""UART commands against an independent AXI-Lite memory, including errors."""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer, with_timeout
import pytest

from axi_lite_slave import AxiLiteSlave
from serial_link import send_bytes, receive_bytes


@cocotb.test()
async def command_protocol_and_axi_errors(dut):
    slave = AxiLiteSlave(dut)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    cocotb.start_soon(slave.run())
    dut.rst.value = 1
    dut.rx.value = 1
    dut.cycle_ct.value = 0x1234
    for _ in range(4):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0

    async def command(request, expected):
        response = cocotb.start_soon(receive_bytes(dut.tx, len(expected)))
        await send_bytes(dut.rx, request)
        assert await with_timeout(response, 100, "us") == expected
        assert not dut.rx_error_o.value

    await command(b"CMDA", b"RESP")
    await command(b"????", b"????")
    await command(b"TEMP", (0x1234).to_bytes(4, "little"))
    address = (0x1000).to_bytes(4, "little")
    data = (0xDEADBEEF).to_bytes(4, "little")
    await command(b"WRIT" + address + data, b"OKAY")
    await command(b"READ" + address, data + b"OKAY")
    slave.next_write_status = 2
    await command(b"WRIT" + address + data, b"ERR!")
    slave.next_read_status = 2
    await command(b"READ" + address, data + b"ERR!")
    assert len(slave.events) == 4
    # A corrupt serial byte invalidates framing: halt until reset, no shifted write.
    response = cocotb.start_soon(receive_bytes(dut.tx, 4))
    for bit in [0] + [1] * 8 + [0]:
        dut.rx.value = bit
        await Timer(80, unit="ns")
    dut.rx.value = 1
    assert await with_timeout(response, 100, "us") == b"ERR!"
    assert dut.rx_error_o.value
    await send_bytes(dut.rx, b"WRIT" + address + data)
    assert len(slave.events) == 4
    await FallingEdge(dut.clk)
    dut.rst.value = 1
    for _ in range(4):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await command(b"CMDA", b"RESP")


@pytest.mark.parametrize("runner", [{"CLK_FREQ": 8000000, "BAUD_RATE": 1000000}], indirect=True)
def test_uart_to_axi(runner):
    runner.test(hdl_toplevel="uart_to_axi", test_module=__name__, test_args=["--trace"])
