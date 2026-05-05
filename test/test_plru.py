import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb import start_soon

import random


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
    i = 0
    w.access_i.value = random.randint(0,3)
    w.access_valid_i.value = 1
    # w.lru_way_ready_i.value = 1
    while True:


        if w.access_ready_o.value == 1 and w.access_valid_i.value == 1:
            w.access_i.value = random.randint(0,3)
            w.access_valid_i.value = 1
            i += 1

        if i == 5:
            w.access_valid_i.value = 0
            break
        await RisingEdge(w.clk_i)

    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
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
