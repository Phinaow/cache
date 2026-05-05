import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb import start_soon


from cocotb_wrapper import *
from verible_struct_parser import *
import generated_config as config

import logging

from util import *

import random

logger = logging.getLogger("cocotb.test")
logger.setLevel(logging.DEBUG)

PERIOD = 20

CACHE_ADDR = 15
MEM_ADDR = 7

config.TAG_SIZE = 3

async def reset(clk, rst):
    # Init and reset
    rst.value = 0
    await Timer(1, units="ns")
    await RisingEdge(clk)
    rst.value = 1
    await RisingEdge(clk)



async def inst_clocks(clk, PERIOD):
    """this instantiates the axi environement & clocks"""
    start_soon(Clock(clk, PERIOD, units="ns").start())

async def emulate_miss(w):
    w.hit_i.value = 0
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    w.hit_i.value = 1



@cocotb.test()
async def main(dut):
    # structs = parse_verible_json("../tree.json")
    # w = wrap_dut(dut, structs)
    # w.register_struct_port("data_i", "cache_op_t")

    structs = parse_verible_json("../tree.json")["structs"]
    w = DutWrapper(dut, structs=structs, port_types={})

    await inst_clocks(w.clk_i, PERIOD)
    await reset(w.clk_i, w.rst_ni)

    i = 0
    jitter = 50

    w.axi_awaddr_i.value = 0
    w.axi_awvalid_i.value = 1
    w.axi_wdata_i.value = 0
    w.axi_wvalid_i.value = 0
    w.axi_wstrb_i.value = 0

    w.axi_bready_i.value = 1

    w.axi_araddr_i.value = 0
    w.axi_arvalid_i.value = 1
    w.axi_rready_i.value = 0

    w.hit_i.value = 0
    w.hit_addr_o.value = 0

    w.ram_data_i.value = 0

    while True:
        await RisingEdge(w.clk_i)
        i += 1
        if i == 10000:
            break

        if w.axi_arready_o.value == 1 and w.axi_arvalid_i.value == 1:
            w.axi_arvalid_i.value = 1
            w.axi_rready_i.value = 1
            cocotb.start_soon(emulate_miss(w))
        elif w.axi_arready_o.value == 1:
            w.axi_araddr_i.value = 12
            w.axi_arvalid_i.value = 1
            w.axi_rready_i.value = 1

        if w.axi_rready_i.value == 1 and w.axi_rvalid_o.value == 1:
            w.hit_i.value = 0


        if w.axi_awready_o.value == 1 and w.axi_awvalid_i.value == 1:
            w.axi_awvalid_i.value = 0
            w.axi_wvalid_i.value = 1
            cocotb.start_soon(emulate_miss(w))

        if w.axi_wvalid_i.value == 1 and w.axi_wready_o.value == 1:
            w.hit_i.value = 0
            break


    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)



def test_transaction(runner):
    runner.test(
        hdl_toplevel="transaction",
        test_module=__name__,
        test_args=["--trace"]
    )
