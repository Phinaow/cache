import cocotb
from cocotb.triggers import Timer, RisingEdge, ReadWrite
from cocotb.clock import Clock
from cocotb import start_soon


from cocotb_wrapper import *
from verible_struct_parser import *

import logging

from util import *

import numpy as np
import random

from drivers.axi_driver import SlaveAxiDriver, MasterAxiDriver

from models.theoretical_dram_model import DRAM
from bitstring import BitArray

from dataclasses import dataclass


logger = logging.getLogger("cocotb.test")
logger.setLevel(logging.DEBUG)

PERIOD = 20

@dataclass
class Block:
    size: int
    addr: int
    data: List[int]
    strb: List[int]

    @classmethod
    def create_random(cls, min_size: int, max_size: int):

        size = random.randint(min_size, max_size)
        addr = random.randint(0, 2**26 - 1) << 2


        data = [random.getrandbits(32) for _ in range(size)]
        strb = [random.randint(0, 0xF) for _ in range(size)]

        return cls(size=size, addr=addr, data=data, strb=strb)

def create_mask(strb) -> int:
    strb = BitArray(uint=strb, length=4)
    mask = BitArray(uint=0x0, length=32)
    for i in range(4):
        if strb[i]:
            mask[i*8:(i+1)*8] = 0xFF

    return mask.uint


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

async def ram_sim(ram: DRAM, dut):
    i = 0
    while not ram.interrupted:
        if dut.ram_we_o.value != 0:
            # ram[int(dut.ram_addr_o.value)] = int(dut.ram_data_o.value)
            await ram.set(int(dut.ram_addr_o.value), int(dut.ram_data_o.value), strb=int(dut.ram_we_o.value))
        # dut.ram_data_i.value = int(ram.get(int(dut.ram_addr_o.value), 0))
        dut.ram_data_i.value = await ram.get(int(dut.ram_addr_o.value))

        await RisingEdge(dut.clk_i)

async def dram_sim(dram: DRAM, ram: DRAM, dut: SimHandleBase):
    i = 0
    dut.cdc_req_ready_i.value  = 0
    dut.cdc_resp_valid_i.value = 0
    while not dram.interrupted:

        if dut.cdc_req_valid_o.value == 1 and dut.cdc_req_ready_i.value == 1:
            dut.cdc_req_ready_i.value = 0
            if dut.cdc_req_data_o.wb_rf.value == 1:
                data_from_ram = await ram.get(int(dut.cdc_req_data_o.cache_addr.value), 63, nb_octet=16)
                await dram.set(int(dut.cdc_req_data_o.mem_addr.value), data_from_ram, awlen=63)
                dut.cdc_resp_valid_i.value = 1
                await until(dut.clk_i, lambda: (dut.cdc_resp_ready_o.value == 1 or dram.interrupted))
                dut.cdc_resp_valid_i.value = 0
            else:
                data_from_dram = await dram.get(int(dut.cdc_req_data_o.mem_addr.value), arlen=63)
                await ram.set(int(dut.cdc_req_data_o.cache_addr.value), data_from_dram, awlen=63, nb_octet=16)
                dut.cdc_resp_valid_i.value = 1
                await until(dut.clk_i, lambda: (dut.cdc_resp_ready_o.value == 1 or dram.interrupted))
                dut.cdc_resp_valid_i.value = 0

        dut.cdc_req_ready_i.value = 1

        await RisingEdge(dut.clk_i)

@cocotb.test()
async def main(dut):
    # structs = parse_verible_json("../tree.json")
    # w = wrap_dut(dut, structs)
    # w.register_struct_port("data_i", "cache_op_t")

    structs = parse_verible_json("../tree.json")["structs"]
    w = DutWrapper(dut, structs=structs, port_types={"cdc_req_data_o": "cdc_data_t"})
    memory = DRAM(w.clk_i, 128, average_latency=60, std_latency=10)
    ram = DRAM(w.clk_i, average_latency=0)

    await inst_clocks(w.clk_i, PERIOD)
    await reset(w.clk_i, w.rst_ni)

    i = 0

    w.axi_awaddr_i.value     = 0
    w.axi_awvalid_i.value    = 0
    w.axi_wdata_i.value      = 0
    w.axi_wvalid_i.value     = 0
    w.axi_wstrb_i.value      = 0xF
    w.axi_bready_i.value     = 0
    w.axi_araddr_i.value     = 0
    w.axi_arvalid_i.value    = 0
    w.axi_rready_i.value     = 0
    w.cdc_req_ready_i.value  = 1
    w.cdc_resp_valid_i.value = 1
    w.ram_data_i.value       = 5

    np.random.seed(42)
    random.seed(42)

    TEST_SIZE = 10

    # addr = [random.randint(0, 2**32 - 1) for _ in range(TEST_SIZE)] #random.randint(0, 2**32, (TEST_SIZE,))
    # data = [random.randint(0, 2**32 - 1) for _ in range(TEST_SIZE)] #random.randint(0, 2**32, (TEST_SIZE,))

    cocotb.start_soon(ram_sim(ram, w))
    cocotb.start_soon(dram_sim(memory, ram, w))
    cocotb.start_soon(cycles_timeout(w.clk_i, 1000000))

    mst = MasterAxiDriver.from_dut(w, "axi", jitter=0)

    # await memory.set(0, [1, 4, 2], awlen=2, strb=0x00FF)
    # val = await memory.get(0, 2)

    # print(f'{val}')


    # for item_addr, item_data in zip(addr, data):
    #     await mst.write.aw.push(int(item_addr))
    #     await mst.write.w.push(int(item_data))
    #     await until(w.clk_i, lambda: mst.write.w.empty())
    # batch = [Block.create_random(50, 100) for _ in range(5)]
    # batch += batch[1:3]
    i = 0
    for i in range(TEST_SIZE):
        batch = [Block.create_random(50, 300) for _ in range(10)]
        # batch.append(batch[0])


        l = 0
        for b in batch:
            addr = list(range(b.addr, b.addr+b.size*4 - 1, 4))
            print(f"batch : {l} size: {b.size}")
            l += 1
            await mst.write(b.data, addr, b.strb)
            await until(w.clk_i, lambda: mst.w_nelem == 0)

        for b in batch:
            addr = list(range(b.addr, b.addr+b.size*4-1, 4))
            await mst.read(addr)
            await until(w.clk_i, lambda: mst.ar_nelem == 0)

            # for d, a, s in zip(b.data, addr, b.strb):
            #     task_write = cocotb.start_soon(mst.write(d, a, 0xF))
            #     task_read = cocotb.start_soon(mst.read(a))

            #     await task_write
            #     await task_read

            await until(w.clk_i, lambda: mst.r_nelem == len(addr))
            result = await mst.get_read_elem()
            await until(w.clk_i, lambda: mst.r_nelem == 0)

            for real, theoretical, strb in zip(result, b.data, b.strb):

                mask = create_mask(strb)
                theoretical = theoretical & mask
                real = real & mask

                assert real == theoretical, f'{real}, {theoretical}, strb={strb} iter={i}'
                # print(f'{real}, {theoretical}, strb={strb} iter={i}')
                i += 1
                # print(f'SUCCESS ADDR {l}')

            result.clear()


    # await mst.write(data, addr)
    # await until(w.clk_i, lambda: mst.w_nelem == 0)
    # await mst.read(addr)
    # await until(w.clk_i, lambda: mst.ar_nelem == 0)

    # result = await mst.get_read_elem()

    # for real, theoretical in zip(result, data):
    #     assert real == theoretical, f'{real}, {theoretical}'

    # for item_addr, item_data in zip(addr, data):

    #     # item_data = BitArray(uint=item_data, length=32)
    #     # item_data = item_data[0:8].uint * 2**24

    #     item_data = item_data & 0xFF000000

    #     await mst.read.ar.push(int(item_addr))
    #     await until(w.clk_i, lambda: (w.axi_arvalid_i.value and w.axi_arready_o.value))
    #     ram_addr = int(w.axi_araddr_i.value)
    #     actual = await mst.read.r.pop()
    #     actual = int(actual) & 0xFF000000
    #     assert item_data == int(actual), f"{item_data} != {int(actual)}, addr{ram_addr}, item_addr{item_addr}"

    await mst.stop()
    ram.interrupt()
    memory.interrupt()


    # await mst.stop()
    # await slv.stop()
    await cycles(dut.clk_i, 10)


def test_cache_controller(runner):
    runner.test(
        hdl_toplevel="cache_controller",
        test_module=__name__,
        test_args=["--trace"]
    )
