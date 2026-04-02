import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb import start_soon
import types


from cocotb_wrapper import *
from verible_struct_parser import *
from generated_config import result

import logging

from util import *

logger = logging.getLogger("cocotb.test")
logger.setLevel(logging.DEBUG)

CPU_PERIOD = 20

CACHE_ADDR = 15
MEM_ADDR = 7


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
    # structs = parse_verible_json("../tree.json")
    # w = wrap_dut(dut, structs)
    # w.register_struct_port("data_i", "cache_op_t")  # ← ajout

    # structs = parse_verible_json("../tree.json")["structs"]
    w = DutWrapper(dut, structs=result["structs"], port_types={"data_i": "cdc_data_t"})

    cache = list(range(100))
    dram = 100 * [None]

    await inst_clocks(w)
    await reset(w)

    w.data_i.mem_addr.value    = MEM_ADDR
    w.data_i.nb_transfer.value = 0b00001111
    w.data_i.cache_addr.value  = CACHE_ADDR
    w.data_i.wb_rf.value = 1


    w.addr_valid_i.value   = 0

    w.axi_awready_i.value  = 0
    w.axi_wready_i.value   = 0

    w.axi_bresp_i.value  = 0
    w.axi_bvalid_i.value = 0

    await RisingEdge(w.clk_i)  # commit auto déclenché ici

    w.addr_valid_i.value = 1

    start_writeback = False
    i = 0

    nb_transfer = None

    addr = 0

    while True:

        await RisingEdge(w.clk_i)

        # Read dram
        if(w.axi_awvalid_o.value == 1):
            addr = int(w.axi_awaddr_o.value)
            nb_transfer = w.axi_awlen_o.value
            w.axi_awready_i.value = 1

        if(w.axi_awvalid_o.value == 1 and w.axi_awready_i.value == 1):
            start_writeback = True
            w.axi_awready_i.value = 0

        if(start_writeback):
            w.axi_wready_i.value = 1
        else:
            w.axi_wready_i.value = 0


        if w.axi_wlast_o.value == 1:
            start_writeback = False
            w.axi_wready_i.value = 0
            w.axi_bresp_i.value = 0
            w.axi_bvalid_i.value = 1

        w.ram_data_i.value = cache[int(w.ram_addr_o.value)]

        if(w.axi_wvalid_o.value == 1 and w.axi_wready_i.value == 1):
            dram[addr+i] = int(w.axi_wdata_o.value)
            i += 1

        if w.axi_bready_o.value == 1 and w.axi_bvalid_i.value == 1:
            w.addr_valid_i.value = 0
            w.axi_bvalid_i.value = 0

        if w.addr_valid_i.value == 1 and w.addr_ready_o.value == 1:
            break

    await RisingEdge(w.clk_i)

    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)

    w.addr_valid_i.value = 1

    while True:

        await RisingEdge(w.clk_i)

        # Read dram
        if(w.axi_awvalid_o.value == 1):
            addr = int(w.axi_awaddr_o.value)
            nb_transfer = w.axi_awlen_o.value
            w.axi_awready_i.value = 1

        if(w.axi_awvalid_o.value == 1 and w.axi_awready_i.value == 1):
            start_writeback = True
            w.axi_awready_i.value = 0

        if(start_writeback):
            w.axi_wready_i.value = 1
        else:
            w.axi_wready_i.value = 0


        if w.axi_wlast_o.value == 1:
            start_writeback = False
            w.axi_wready_i.value = 0
            w.axi_bresp_i.value = 0
            w.axi_bvalid_i.value = 1

        w.ram_data_i.value = cache[int(w.ram_addr_o.value)]

        if(w.axi_wvalid_o.value == 1 and w.axi_wready_i.value == 1):
            dram[addr+i] = int(w.axi_wdata_o.value)
            i += 1

        if w.axi_bready_o.value == 1 and w.axi_bvalid_i.value == 1:
            w.addr_valid_i.value = 0
            w.axi_bvalid_i.value = 0

        if w.addr_valid_i.value == 1 and w.addr_ready_o.value == 1:
            break


    for verif in range(int(nb_transfer)):
        assert cache[verif+CACHE_ADDR] == dram[verif+MEM_ADDR], f"Value {dram}"



def test_refill_engine(runner):
    runner.test(
        hdl_toplevel="writeback_engine",
        test_module=__name__,
        test_args=["--trace"]
    )
