import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb import start_soon


from cocotb_wrapper import *
from verible_struct_parser import *

import logging

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

    structs = parse_verible_json("../tree.json")["structs"]
    w = DutWrapper(dut, structs=structs, port_types={"data_i": "cdc_data_t"})

    dram = list(range(100))
    cache = 100 * [None]

    await inst_clocks(dut)
    await reset(dut)

    w.data_i.mem_addr.value    = MEM_ADDR
    w.data_i.nb_transfer.value = 0b000011
    w.data_i.cache_addr.value  = CACHE_ADDR
    w.data_i.wb_rf.value = 0


    # commit auto au prochain await, pas besoin de commit() manuel
    w.addr_valid_i.value = 0
    w.axi_arready_i.value  = 0
    w.axi_rdata_i.value    = 0
    w.axi_rlast_i.value    = 0
    w.axi_rvalid_i.value   = 0

    await RisingEdge(w.clk_i)  # commit auto déclenché ici

    w.addr_valid_i.value = 1

    start_refill = False
    i = 0

    nb_transfer = None

    addr = 0

    while True:

        await RisingEdge(w.clk_i)

        if(w.ram_we_o.value != 0):
            cache[int(w.ram_addr_o.value)] = int(w.ram_data_o.value)

        if(w.axi_arvalid_o.value == 1):
            addr = int(w.axi_araddr_o.value)
            nb_transfer = w.axi_arlen_o.value
            w.axi_arready_i.value = 1

        if(w.axi_arvalid_o.value == 1 and w.axi_arready_i.value == 1):
            start_refill = True
            w.axi_arready_i.value = 0

        if(start_refill):
            w.axi_rvalid_i.value = 1
            if(w.axi_rready_o.value == 1 and w.axi_rvalid_i.value == 1):
                i += 1

        w.axi_rdata_i.value = dram[addr+i]

        if nb_transfer is not None and i == int(nb_transfer)-1:
            w.axi_rlast_i.value = 1
        else:
            w.axi_rlast_i.value = 0

        if(w.addr_ready_o.value == 1):
            w.addr_valid_i.value = 0
            w.axi_rvalid_i.value = 0
            break

    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)
    await RisingEdge(w.clk_i)

    w.addr_valid_i.value = 1
    i=0
    start_refill = False

    while True:

        await RisingEdge(w.clk_i)

        if(w.ram_we_o.value != 0):
            cache[int(w.ram_addr_o.value)] = int(w.ram_data_o.value)

        if(w.axi_arvalid_o.value == 1):
            addr = int(w.axi_araddr_o.value)
            nb_transfer = w.axi_arlen_o.value
            w.axi_arready_i.value = 1

        if(w.axi_arvalid_o.value == 1 and w.axi_arready_i.value == 1):
            start_refill = True
            w.axi_arready_i.value = 0

        if(start_refill):
            w.axi_rvalid_i.value = 1
            if(w.axi_rready_o.value == 1 and w.axi_rvalid_i.value == 1):
                i += 1

        w.axi_rdata_i.value = dram[addr+i]

        if nb_transfer is not None and i == int(nb_transfer)-1:
            w.axi_rlast_i.value = 1
        else:
            w.axi_rlast_i.value = 0

        if(w.addr_ready_o.value == 1):
            w.addr_valid_i.value = 0
            break


    for verif in range(int(nb_transfer)):
        assert cache[verif+CACHE_ADDR] == dram[verif+MEM_ADDR], f"Value {cache}"



def test_refill_engine(runner):
    runner.test(
        hdl_toplevel="refill_engine",
        test_module=__name__,
        test_args=["--trace"]
    )
