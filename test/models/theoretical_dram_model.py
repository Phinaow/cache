from __future__ import annotations
from abc import abstractmethod
from cocotb.triggers import Combine, Waitable, RisingEdge
from cocotb.handle import SimHandleBase
from typing import Optional, List, TypeVar, Type, Union
import random

from util import until

from bitstring import BitArray


class DRAM():

    def __init__(
        self,
        clk: SimHandleBase,
        data_size: int = 32,
        average_latency: int = 1,
        std_latency: int = 0,
        latency_per_transaction: int = 0,
        strb: BitArray = BitArray(uint=0xFFFF, length=16),
        *args,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs,
    ) -> None:

        self.clk = clk

        self.jitter = jitter
        self.capacity = capacity

        self.data_size = data_size

        self.std = std_latency
        self.latency = average_latency
        self.latency_per_transaction = latency_per_transaction

        self.interrupted = False

        self.__dram = {}

        self.strb = strb

    async def get(self, key, arlen: int = 0, nb_octet: int = None) -> Union[List, int]:

        read_data = []
        std = random.randint(0, self.std)

        nb_octet = int(self.data_size/8) if nb_octet is None else nb_octet

        data = BitArray(length=int(nb_octet*8))

        for i in range(arlen + 1):
            for o in range(nb_octet):
                data[o*8:(o+1)*8] = self.__dram.get(key*nb_octet + i*nb_octet + o, random.randint(0, 2**8 - 1))
            for _ in range(self.latency_per_transaction):
                await RisingEdge(self.clk)

            data.byteswap()
            read_data.append(data.uint)

        for _ in range(self.latency + std):
            await RisingEdge(self.clk)

        if arlen == 0:
            return read_data[0]
        else:
            return read_data


    async def set(self, key, value: Union[List, int], strb: int = None, awlen: int = 0, nb_octet: int = None) -> None:

        std = random.randint(0, self.std)
        nb_octet = int(self.data_size/8) if nb_octet is None else nb_octet

        if strb is None:
            strb = BitArray(uint=0x0, length=nb_octet)
            strb.invert()
        else:
            strb = BitArray(uint=strb, length=nb_octet)
            strb.reverse()


        for i in range(awlen + 1):

            data = value if isinstance(value, int) else value.pop(0)

            # data = value.pop(0)
            data = BitArray(uint=data, length=nb_octet*8)
            data.byteswap()
            for o in range(nb_octet):
                if strb[o]:
                    self.__dram[key*nb_octet + nb_octet*i + o] = data[o*8:(o+1)*8].uint

            for _ in range(self.latency_per_transaction):
                await RisingEdge(self.clk)

        for _ in range(self.latency + std):
            await RisingEdge(self.clk)

    def __getitem__(self, key):
        return self.__dram.get(key, None)

    def __setitem__(self, key, value):
        self.__dram[key] = value


    def interrupt(self) -> None:
        """
        Interrupts the driver.
        """
        self.interrupted = True
