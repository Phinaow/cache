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

PERIOD = 20

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



@cocotb.test()
async def main(dut):
    # structs = parse_verible_json("../tree.json")
    # w = wrap_dut(dut, structs)
    # w.register_struct_port("data_i", "cache_op_t")

    structs = parse_verible_json("../tree.json")["structs"]
    w = DutWrapper(dut, structs=structs, port_types={"cdc_data_o": "cdc_data_t"})

    await inst_clocks(w.clk_i, PERIOD)
    await reset(w.clk_i, w.rst_ni)

    w.axi_awvalid_i.value = 1
    w.axi_awaddr_i.value = 4*8
    w.axi_wstrb_i.value = 0b1111

    timer = 0

    cache = list(range(512))

    while True:

        if(w.ram_we_o.value != 0):
            cache[int(w.ram_addr_o.value)] = int(w.ram_data_o.value)

        w.ram_data_i.value = cache[int(w.ram_addr_o.value)]

        if(w.cdc_valid_o.value == 1):
            w.cdc_ready_i.value = 1

        if(w.cdc_valid_o.value == 1 and w.cdc_ready_i.value == 1):
            w.cdc_ready_i.value = 0

        if(w.axi_awvalid_i.value == 1 and w.axi_awready_o.value == 1):
            w.axi_awvalid_i.value = 0
            w.axi_wvalid_i.value = 1
            w.axi_wdata_i.value = 12345

        if(w.axi_wvalid_i.value == 1 and w.axi_wready_o.value == 1):
            w.axi_wvalid_i.value = 0
            w.axi_bready_i.value = 1

        if(w.axi_bready_i.value == 1 and w.axi_bvalid_o.value == 1):
            w.axi_bready_i.value = 0
            break

        timer += 1

        if timer >= 10000:
            assert 1 == 0, f"Time verflow"
            break

        await RisingEdge(w.clk_i)


    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)

    timer = 0
    w.axi_awvalid_i.value = 1
    w.axi_awaddr_i.value = 4*9
    w.axi_wstrb_i.value = 0b1111
    w.axi_bready_i.value = 1

    while True:

        if(w.ram_we_o.value != 0):
            cache[int(w.ram_addr_o.value)] = int(w.ram_data_o.value)

        w.ram_data_i.value = cache[int(w.ram_addr_o.value)]

        if(w.cdc_valid_o.value == 1):
            w.cdc_ready_i.value = 1

        if(w.cdc_valid_o.value == 1 and w.cdc_ready_i.value == 1):
            w.cdc_ready_i.value = 0

        if(w.axi_awvalid_i.value == 1 and w.axi_awready_o.value == 1):
            w.axi_awvalid_i.value = 0
            w.axi_wvalid_i.value = 1
            w.axi_wdata_i.value = 5678

        if(w.axi_wvalid_i.value == 1 and w.axi_wready_o.value == 1):
            w.axi_wvalid_i.value = 0
            w.axi_bready_i.value = 1

        if(w.axi_bready_i.value == 1 and w.axi_bvalid_o.value == 1):
            w.axi_bready_i.value = 0
            break

        timer += 1

        if timer >= 10000:
            assert 1 == 0, f"Time verflow"
            break

        await RisingEdge(w.clk_i)

    for i in range(10):
        await RisingEdge(w.clk_i)
        await RisingEdge(w.clk_i)
        await RisingEdge(w.clk_i)
        await RisingEdge(w.clk_i)

        timer = 0
        w.axi_awvalid_i.value = 1
        w.axi_awaddr_i.value = 2**11 * i
        w.axi_wstrb_i.value = 0b1111
        # w.axi_bready_i.value = 1

        while True:

            if(w.ram_we_o.value != 0):
                cache[int(w.ram_addr_o.value)] = int(w.ram_data_o.value)

            w.ram_data_i.value = cache[int(w.ram_addr_o.value)]

            if(w.cdc_valid_o.value == 1):
                w.cdc_ready_i.value = 1

            if(w.cdc_valid_o.value == 1 and w.cdc_ready_i.value == 1):
                w.cdc_ready_i.value = 0

            if(w.axi_awvalid_i.value == 1 and w.axi_awready_o.value == 1):
                w.axi_awvalid_i.value = 0
                w.axi_wvalid_i.value = 1
                w.axi_wdata_i.value = 3456789

            if(w.axi_wvalid_i.value == 1 and w.axi_wready_o.value == 1):
                w.axi_wvalid_i.value = 0
                w.axi_bready_i.value = 1

            if(w.axi_bready_i.value == 1 and w.axi_bvalid_o.value == 1):
                w.axi_bready_i.value = 0
                break

            timer += 1

            if timer >= 10000:
                assert 1 == 0, f"Time verflow"
                break

            await RisingEdge(w.clk_i)

    print(cache)






def test_cache_controller(runner):
    runner.test(
        hdl_toplevel="cache_controller",
        test_module=__name__,
        test_args=["--trace"]
    )
