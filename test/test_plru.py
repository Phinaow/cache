import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb import start_soon


from generated_config import result
from cocotb_wrapper import DutWrapper


import logging

from util import *

logger = logging.getLogger("cocotb.test")
logger.setLevel(logging.DEBUG)

CPU_PERIOD = 20

async def reset(dut):
    # Init and reset
    dut.rst_ni.value = 0
    await Timer(1, units="ns")
    await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)



async def inst_clocks(dut):
    """this instantiates the axi environement & clocks"""
    start_soon(Clock(dut.clk_i, CPU_PERIOD, units="ns").start())



@cocotb.test()
async def main(dut):

    # structs = parse_verible_json("../tree.json")["structs"]

    # port_types={}

    w = DutWrapper(dut, structs=result["structs"], port_types={})

    await inst_clocks(w)
    await reset(w)

    await RisingEdge(w.clk_i)

    w.access_i.value = 0

    for i in range(10):
        w.access_i.value = 2**0
        await RisingEdge(w.clk_i)
        w.access_i.value = 2**2
        await RisingEdge(w.clk_i)

    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)



def test_plru(runner):
    runner.test(
        hdl_toplevel="plru",
        test_module=__name__,
        test_args=["--trace"]
    )
