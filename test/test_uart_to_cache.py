"""Board top from serial pins to the cache and the functional MIG substitute."""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, with_timeout
import pytest

from serial_link import send_bytes, receive_bytes


@cocotb.test()
async def serial_write_read_evictions_and_errors(dut):
    cocotb.start_soon(Clock(dut.sys_clk_i, 10, unit="ns").start())
    dut.sys_rst.value = 0
    dut.rx.value = 1
    for _ in range(5):
        await RisingEdge(dut.sys_clk_i)
    await FallingEdge(dut.sys_clk_i)
    dut.sys_rst.value = 1

    async def command(request, expected):
        response = cocotb.start_soon(receive_bytes(dut.tx, len(expected)))
        await send_bytes(dut.rx, request)
        assert await with_timeout(response, 100, "us") == expected

    await command(b"CMDA", b"RESP")
    words = {tag * 1024: 0xCAFE0000 + tag for tag in range(12)}
    for address, word in words.items():
        await command(b"WRIT" + address.to_bytes(4, "little") + word.to_bytes(4, "little"), b"OKAY")
    for address, word in words.items():
        await command(b"READ" + address.to_bytes(4, "little"), word.to_bytes(4, "little") + b"OKAY")
    await command(b"WRIT" + (0x20000000).to_bytes(4, "little") + bytes(4), b"ERR!")
    await command(b"READ" + (1).to_bytes(4, "little"), bytes(4) + b"ERR!")
    assert int(dut.led.value) == 1, "Unexpected UART error indication"


@pytest.mark.parametrize("runner", [{"USE_VENDOR_RAM": 0, "CPU_CLK_FREQ": 8000000,
                                     "BAUD_RATE": 1000000}], indirect=True)
def test_uart_to_cache(runner):
    runner.test(hdl_toplevel="uart_to_cache", test_module=__name__, test_args=["--trace"])
