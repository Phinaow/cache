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

CPU_PERIOD = 20

REFILL = 0
WRITEBACK = 1

MEM_ADDR = 5
CACHE_ADDR = 96

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

    cache = list(range(1000))
    dram = list(range(1000))

    addr = 0
    nb_transfer = None
    i = 0

    start_refill = False
    start_writeback = True

    structs = parse_verible_json("../tree.json")["structs"]

    port_types={"cdc_data_i": "cdc_data_t"}

    w = DutWrapper(dut, structs=structs, port_types=port_types)

    await inst_clocks(w)
    await reset(w)

    w.cdc_data_i.mem_addr.value  = 0
    w.cdc_data_i.nb_transfer.value = 31
    w.cdc_data_i.cache_addr.value = CACHE_ADDR

    w.cdc_valid_i.value = 0

    w.ram_data_i.value = 0

    w.m_axi_awready.value = 0

    w.m_axi_wready.value = 0

    w.m_axi_bid.value    = 0
    w.m_axi_bresp.value  = 0
    w.m_axi_bvalid.value = 0

    w.m_axi_arready.value = 0

    w.m_axi_rid.value    = 0
    w.m_axi_rdata.value  = 0
    w.m_axi_rresp.value  = 0
    w.m_axi_rlast.value  = 0
    w.m_axi_rvalid.value = 0

    await RisingEdge(w.clk_i)

    w.cdc_data_i.mem_addr.value  = 0
    w.cdc_data_i.wb_rf.value = REFILL
    w.cdc_valid_i.value = 1

    w.resp_ready_i.value = 1
    wait = 0
    iteration = 0
    tsts = 0
    while True:
        await RisingEdge(w.clk_i)

        if(w.ram_we_o.value != 0):
            cache[int(w.ram_addr_o.value)] = int(w.ram_data_o.value)

        w.ram_data_i.value = cache[int(w.ram_addr_o.value)]

        if(w.m_axi_arvalid.value == 1):
            addr = int(w.m_axi_araddr.value)
            nb_transfer = int(w.m_axi_arlen.value)
            w.m_axi_arready.value = 1

        if w.m_axi_arvalid.value == 1 and w.m_axi_arready.value == 1:
            w.m_axi_arready.value = 0
            start_refill = True

        if w.m_axi_rvalid.value == 1 and w.m_axi_rready.value == 1:
            i += 1
            w.m_axi_rvalid.value = 0

        if w.m_axi_rlast.value == 1:
            w.m_axi_rlast.value = 0

        if start_refill:
            w.m_axi_rdata.value = dram[addr+i]
            if tsts == 30:
                w.m_axi_rvalid.value = 0
            else:
                w.m_axi_rvalid.value = 1
            tsts += 1

        if nb_transfer is not None and i == nb_transfer:
            w.m_axi_rlast.value = 1


        if w.resp_ready_i.value == 1 and w.resp_valid_o.value == 1:
            assert w.resp_data_o.value == 0
            for verif in range(int(nb_transfer)):
                assert cache[verif+CACHE_ADDR] == dram[verif+iteration], f"Value {cache[0:128]} :: {iteration}"
            iteration += 1
            w.cdc_data_i.mem_addr.value = iteration
            start_refill = False
            i = 0

        if iteration == 1:
            w.cdc_valid_i.value = 0
            break

        wait += 1
        if wait == 10000:
            assert 1 == 0, f"Failed to transfer the data"
            break

    # await RisingEdge(w.clk_i)
    # await RisingEdge(w.clk_i)
    # await RisingEdge(w.clk_i)
    # await RisingEdge(w.clk_i)
    # await RisingEdge(w.clk_i)

    w.cdc_data_i.mem_addr.value  = 0
    w.cdc_data_i.wb_rf.value = WRITEBACK
    w.cdc_valid_i.value = 1
    wait = 0
    iteration = 0
    i = 0

    while True:
        await RisingEdge(w.clk_i)

        # w.m_axi_arready.value = 1
        # w.m_axi_rvalid.value = 1
        # w.m_axi_rlast.value = 1

        if(w.ram_we_o.value != 0):
            cache[int(w.ram_addr_o.value)] = int(w.ram_data_o.value)

        w.ram_data_i.value = cache[int(w.ram_addr_o.value)]

        if w.m_axi_awvalid.value == 1:
            addr = int(w.m_axi_awaddr.value)
            nb_transfer = int(w.m_axi_awlen.value)
            w.m_axi_awready.value = 1

        if w.m_axi_awvalid.value == 1 and w.m_axi_awready.value == 1:
            w.m_axi_awready.value = 0
            start_writeback = True

        if w.m_axi_wvalid.value == 1:
            dram[addr+i] = int(w.m_axi_wdata.value)
            w.m_axi_wready.value = 1

        if w.m_axi_wready.value == 1 and w.m_axi_wvalid.value == 1:
            # w.m_axi_wready.value = 0
            i += 1

        if w.m_axi_wlast.value == 1:
            w.m_axi_wready.value = 0

        if w.m_axi_bready.value == 1:
            w.m_axi_bvalid.value = 1
            w.m_axi_bresp.value = 0
        if w.m_axi_bvalid.value == 1 and w.m_axi_bready.value == 1:
            w.m_axi_bvalid.value = 0

        if w.resp_ready_i.value == 1 and w.resp_valid_o.value == 1:
            assert w.resp_data_o.value == 1
            for verif in range(int(nb_transfer)):
                pass
                #assert cache[CACHE_ADDR+verif] == dram[verif+iteration+5], f"Value {cache[0:128]} :: {iteration}"
            iteration += 1
            w.cdc_data_i.mem_addr.value = 36
            i = 0

        if iteration == 1:
            w.cdc_valid_i.value = 0
            break

        wait += 1
        if wait == 10000:
            assert 1 == 0, f"Failed to transfer the data"
            break

    print(dram, cache)


def test_miss_handler(runner):
    runner.test(
        hdl_toplevel="miss_handler",
        test_module=__name__,
        test_args=["--trace"]
    )
