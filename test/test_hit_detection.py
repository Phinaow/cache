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



@cocotb.test()
async def main(dut):
    # structs = parse_verible_json("../tree.json")
    # w = wrap_dut(dut, structs)
    # w.register_struct_port("data_i", "cache_op_t")

    structs = parse_verible_json("../tree.json")["structs"]
    w = DutWrapper(dut, structs=structs, port_types={"cdc_req_data_o": "cdc_data_t"})

    await inst_clocks(w.clk_i, PERIOD)
    await reset(w.clk_i, w.rst_ni)

    i = 0
    jitter = 50

    w.awvalid_i.value = 0
    w.awaddr_i.value = 0
    w.arvalid_i.value = 0
    w.araddr_i.value = 0



    w.cdc_req_ready_i.value = 0

    w.cdc_resp_valid_i.value = 0

    w.access_ready_i.value = 1

    start_new_tr = True

    write_before = False

    while True:
        await RisingEdge(w.clk_i)

        # if w.cdc_req_valid_o.value == 1 and w.cdc_req_ready_i.value == 1:
        #     w.cdc_req_ready_i.value = 0

        #     await RisingEdge(w.clk_i)
        #     await RisingEdge(w.clk_i)
        #     await RisingEdge(w.clk_i)
        #     await RisingEdge(w.clk_i)

        #     w.cdc_resp_valid_i.value = 1
        # elif w.cdc_req_valid_o.value == 1:
        #     w.cdc_req_ready_i.value = 1

        # if w.cdc_resp_valid_i.value == 1 and w.cdc_resp_ready_o.value == 1:
        #     w.cdc_resp_valid_i.value = 0

        # if w.hit_o.value == 1:
        #     w.awaddr_i.value = random.randint(0, 2**config.TAG_SIZE) # 2**i
        #     i += 1

        # if i == 15:
        #     break

        if w.access_valid_o.value == 1:
            w.access_ready_i.value = 0
            w.lru_way_valid_i.value = 0
            w.lru_way_data_i.value = random.randint(0, 3)
        else:
            w.access_ready_i.value = 1
            w.lru_way_valid_i.value = 1

        if(random.randint(0, jitter) == 0 and start_new_tr):
            start_new_tr = False
            tr_type = random.randint(0, 1)
            if(tr_type == 0):
                w.awvalid_i.value = 1
                last_write_addr = random.randint(0, 2**config.TAG_SIZE)
                w.awaddr_i.value = last_write_addr
                write_before = True
            else:
                w.arvalid_i.value = 1
                last_addr_read = random.randint(0, 2**config.TAG_SIZE)
                w.araddr_i.value = last_addr_read
        elif w.hit_o.value == 1:
            w.awvalid_i.value = 0
            w.arvalid_i.value = 0

        if w.cdc_req_valid_o.value == 1:
            w.cdc_req_ready_i.value = 1

        if w.cdc_req_valid_o.value == 1 and w.cdc_req_ready_i.value == 1:
            w.cdc_req_ready_i.value = 0
            # assert int(w.cdc_req_data_o.mem_addr.value) == int(w.awaddr_i.value) << config.WORD_POS, \
            #     f"{int(w.cdc_req_data_o.mem_addr.value)} != {int(w.awaddr_i.value) << config.WORD_POS}"

            await RisingEdge(w.clk_i)
            await RisingEdge(w.clk_i)
            await RisingEdge(w.clk_i)
            await RisingEdge(w.clk_i)

            w.cdc_resp_valid_i.value = 1

        if w.cdc_resp_valid_i.value == 1 and w.cdc_resp_ready_o.value == 1:
            w.cdc_resp_valid_i.value = 0

        if w.hit_o.value == 1:
            start_new_tr = True
            # w.awaddr_i.value = random.randint(0, 2**config.TAG_SIZE) # 2**i
            i += 1

        if i == 100:
            break





def test_hit_detection(runner):
    runner.test(
        hdl_toplevel="hit_detection",
        test_module=__name__,
        test_args=["--trace"]
    )
