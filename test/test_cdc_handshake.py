import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb import start_soon


from cocotb_wrapper import *
from verible_struct_parser import *

import logging

from util import *

logger = logging.getLogger("cocotb.test")
logger.setLevel(logging.DEBUG)

PERIOD_DOMAIN_SRC = 5
PERIOD_DOMAIN_DST = 20

CACHE_ADDR = 15
MEM_ADDR = 7


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


async def from_domain_src(dut):
    nb_transfers = 0
    dut.src_data_i.value = 0
    while True:

        # dut.src_data_i.value = nb_transfers
        dut.src_valid_i.value = 1

        if dut.src_valid_i.value == 1 and dut.src_ready_o.value == 1:
            nb_transfers += 1
            dut.src_data_i.value = nb_transfers
            dut.src_valid_i.value = 0
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)
            await RisingEdge(dut.clk_src_i)

        await RisingEdge(dut.clk_src_i)

        if nb_transfers == 10:
            break

async def from_domain_dst(dut):
    nb_transfers = 0
    while True:
        await RisingEdge(dut.clk_dst_i)

        if dut.dst_valid_o.value == 1 and dut.dst_ready_i.value == 0:
            # assert int(dut.dst_data_o.value) == nb_transfers, f"{int(dut.dst_data_o.value)} != {nb_transfers}"
            await RisingEdge(dut.clk_dst_i)
            await RisingEdge(dut.clk_dst_i)
            await RisingEdge(dut.clk_dst_i)
            await RisingEdge(dut.clk_dst_i)
            await RisingEdge(dut.clk_dst_i)
            await RisingEdge(dut.clk_dst_i)
            await RisingEdge(dut.clk_dst_i)
            await RisingEdge(dut.clk_dst_i)
            dut.dst_ready_i.value = 1

        if dut.dst_valid_o.value == 1 and dut.dst_ready_i.value == 1:
            dut.dst_ready_i.value = 0
            nb_transfers += 1

        if nb_transfers == 10:
            break





@cocotb.test()
async def main(dut):
    # structs = parse_verible_json("../tree.json")
    # w = wrap_dut(dut, structs)
    # w.register_struct_port("data_i", "cache_op_t")  # ← ajout

    structs = parse_verible_json("../tree.json")
    w = DutWrapper(dut, structs=structs, port_types={})

    await inst_clocks(w.clk_src_i, PERIOD_DOMAIN_SRC)
    await inst_clocks(w.clk_dst_i, PERIOD_DOMAIN_DST)
    await reset(w.clk_src_i, w.rst_src_ni)
    await reset(w.clk_dst_i, w.rst_dst_ni)

    w.src_data_i.value = 0
    w.src_valid_i.value = 0

    w.dst_ready_i.value = 0

    await RisingEdge(w.clk_dst_i)
    await RisingEdge(w.clk_src_i)
    await RisingEdge(w.clk_dst_i)
    await RisingEdge(w.clk_src_i)
    await RisingEdge(w.clk_dst_i)
    await RisingEdge(w.clk_src_i)
    await RisingEdge(w.clk_src_i)
    await RisingEdge(w.clk_src_i)

    task_dst = cocotb.start_soon(from_domain_dst(w))
    task_src = cocotb.start_soon(from_domain_src(w))

    # On attend la fin des deux tâches
    await task_dst
    await task_src



def test_cdc_handshake(runner):
    runner.test(
        hdl_toplevel="cdc_handshake",
        test_module=__name__,
        test_args=["--trace"]
    )
