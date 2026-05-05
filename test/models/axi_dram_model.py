from __future__ import annotations
from abc import abstractmethod
from cocotb.triggers import Combine, Waitable, RisingEdge
from cocotb.handle import SimHandleBase
from typing import Optional, List, TypeVar, Type, Union
import random

from util import until


"""
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
----------------------------------------------------------------------------------------------------
--------------------------Need to add the strb it will not work otherwise---------------------------
----------------------------------------------------------------------------------------------------
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""



class DRAM(Waitable):

    def __init__(
        self,
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        clk_name: Optional[str] = 'clk_i',
        *args,
        jitter: int = 0,
        capacity: Optional[int] = None,
        awlen: Optional[int] = None,
        arlen: Optional[int] = None,
        **kwargs,
    ) -> None:
        prefix = "" if prefix is None else f"{prefix}_"

        self.jitter = jitter
        self.capacity = capacity

        self.interrupted = False

        self.__dram = {}

        # self.rd_queue

        self.clk = getattr(dut, f'{clk_name}')

        self.ar_valid = getattr(dut, f'{prefix}arvalid_i')
        self.ar_ready = getattr(dut, f'{prefix}arready_o')
        self.ar_addr  = getattr(dut, f'{prefix}addr_i')
        self.ar_burst

        self.rd_valid = getattr(dut, f'{prefix}rvalid_o')
        self.rd_ready = getattr(dut, f'{prefix}rready_i')
        self.rd_data  = getattr(dut, f'{prefix}rdata_o')
        self.rd_resp  = getattr(dut, f'{prefix}rresp')

        self.aw_valid = getattr(dut, f'{prefix}awvalid_i')
        self.aw_ready = getattr(dut, f'{prefix}awready_o')
        self.aw_addr  = getattr(dut, f'{prefix}awaddr_i')

        self.wr_valid = getattr(dut, f'{prefix}wvalid_i')
        self.wr_ready = getattr(dut, f'{prefix}wready_o')
        self.wr_data  = getattr(dut, f'{prefix}wdata_i')

        self.wr_bvalid = getattr(dut, f'{prefix}bvalid_o')
        self.wr_bready = getattr(dut, f'{prefix}bready_i')
        self.wr_bresp  = getattr(dut, f'{prefix}bresp')

        self.__dut_arlen = False
        self.__dut_awlen = False

        if awlen is None:
            self.awlen = getattr(dut, f'{prefix}awlen_i')
            self.__dut_awlen = True
        else:
            self.awlen = awlen

        if arlen is None:
            self.arlen = getattr(dut, f'{prefix}arlen_i')
            self.__dut_arlen = True
        else:
            self.arlen = arlen

    async def __getitem__(self, key) -> List:
        addr = None
        data_stable = False
        nb_transfers = 0
        i = 0
        read_data = []

        await until(self.clk, lambda: self.rst.value == 1)

        while not self.interrupted:
            if addr is None:
                num = random.randint(0, self.jitter)
                self.ar_ready.value = (num == 0)

                if(self.ar_ready.value == 1 and self.ar_valid == 1):
                    self.ar_addr.value = key
                    addr = key
                    self.ar_ready.value = 0
                    if self.__dut_arlen:
                        nb_transfers = int(self.arlen.value) + 1
                    else:
                        nb_transfers = self.arlen + 1

            elif not data_stable:
                data_stable = (random.randint(0, self.jitter) == 0)

            else:
                self.rd_valid.value = 1
                self.rd_data.value = int(self.__dram.get(int(addr) + i, int()))

                if self.rd_valid.value == 1 and self.rd_ready.value == 1:
                    self.rd_valid.value = 0
                    data_stable = False
                    read_data.append(self.__dram.get(int(addr) + i, None))
                    i += 1

                if i == nb_transfers:
                    break
            await RisingEdge(self.clk)

        return read_data


    async def __setitem__(self, key, value: List) -> None:
        addr = None
        nb_transfers = 0
        i = 0

        await until(self.clk, lambda: self.rst.value == 1)

        while not self.interrupted:
            if addr is None:
                num = random.randint(0, self.jitter)
                self.aw_ready.value = (num == 0)

                if(self.aw_ready.value == 1 and self.aw_valid.value == 1):
                    self.aw_ready.value = 0
                    self.aw_addr.value = key
                    addr = key

                    if self.__dut_awlen:
                        nb_transfers = int(self.awlen.value) + 1
                    else:
                        nb_transfers = self.awlen + 1
            else:
                num = random.randint(0, self.jitter)
                self.wr_ready.value = (num == 0)

                if(self.wr_ready.value == 1 and self.wr_valid.value == 1):
                    data = value.pop(0)
                    self.__dram[int(addr) + i] = data
                    self.wr_data.value = data
                    i += 1

                if(i == nb_transfers):
                    self.wr_ready.value = 0
                    break


            await RisingEdge(self.clk)


    def interrupt(self) -> None:
        """
        Interrupts the driver.
        """
        self.interrupted = True
