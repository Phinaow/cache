from .channel_drivers import SlaveChannelDriver, MasterChannelDriver
from .driver import Driver
from cocotb.handle import SimHandleBase
from cocotb import start_soon
from typing import List, Optional, Type, TypeVar, Union
import numpy as np
from util import until
from cocotb.triggers import RisingEdge

T = TypeVar("T")


class SlaveWriteAxiDriver(Driver):
    def __init__(
        self,
        aw: SlaveChannelDriver,
        w: SlaveChannelDriver,
        b: MasterChannelDriver,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.aw = aw
        self.w = w
        self.b = b

        self.add_trigger(self.aw)
        self.add_trigger(self.w)
        self.add_trigger(self.b)

    def interrupt(self):
        self.aw.interrupt()
        self.w.interrupt()
        self.b.interrupt()

    @classmethod
    def from_dut(
        cls: Type[T],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        dtype: Type = int,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs
    ) -> T:
        prefix = "" if prefix is None else f"{prefix}_"
        return cls(
            aw=SlaveChannelDriver.from_dut(
                dut, f"{prefix}aw", "addr", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            w=SlaveChannelDriver.from_dut(
                dut, f"{prefix}w", "data", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            b=MasterChannelDriver.from_dut(
                dut, f"{prefix}b", "resp", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            *args,
            **kwargs
        )


class SlaveReadAxiDriver(Driver):
    def __init__(
        self,
        ar: SlaveChannelDriver,
        r: MasterChannelDriver,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.ar = ar
        self.r = r

        self.add_trigger(self.ar)
        self.add_trigger(self.r)

    def interrupt(self):
        self.ar.interrupt()
        self.r.interrupt()

    @classmethod
    def from_dut(
        cls: Type[T],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        dtype: Type = int,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs
    ) -> T:
        prefix = "" if prefix is None else f"{prefix}_"
        return cls(
            ar=SlaveChannelDriver.from_dut(
                dut, f"{prefix}ar", "addr", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            r=MasterChannelDriver.from_dut(
                dut, f"{prefix}r", "data", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            *args,
            **kwargs
        )


class SlaveAxiDriver(Driver):
    def __init__(
        self,
        write: Optional[SlaveWriteAxiDriver] = None,
        read: Optional[SlaveReadAxiDriver] = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.write = write
        self.read = read

        if self.write is not None:
            self.add_trigger(self.write)

        if self.read is not None:
            self.add_trigger(self.read)

    def interrupt(self):
        if self.write is not None:
            self.write.interrupt()

        if self.read is not None:
            self.read.interrupt()

        super().interrupt()

    @classmethod
    def from_dut(
        cls: Type[T],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        dtype: Type = int,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs
    ) -> T:
        return cls(
            write=SlaveWriteAxiDriver.from_dut(
                dut, prefix, index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            read=SlaveReadAxiDriver.from_dut(
                dut, prefix, index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            *args,
            **kwargs
        )


class MasterWriteAxiDriver(Driver):
    def __init__(
        self,
        aw: MasterChannelDriver,
        w: MasterChannelDriver,
        b: SlaveChannelDriver,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.aw = aw
        self.w = w
        self.b = b

        self.add_trigger(self.aw)
        self.add_trigger(self.w)
        self.add_trigger(self.b)

    def interrupt(self):
        self.aw.interrupt()
        self.w.interrupt()
        self.b.interrupt()

    @classmethod
    def from_dut(
        cls: Type[T],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        dtype: Type = int,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs
    ) -> T:
        prefix = "" if prefix is None else f"{prefix}_"
        return cls(
            aw=MasterChannelDriver.from_dut(
                dut, f"{prefix}aw", "addr", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            w=MasterChannelDriver.from_dut(
                dut, f"{prefix}w", "data", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            b=SlaveChannelDriver.from_dut(
                dut, f"{prefix}b", "resp", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            *args,
            **kwargs
        )


class MasterReadAxiDriver(Driver):
    def __init__(
        self,
        ar: MasterChannelDriver,
        r: SlaveChannelDriver,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.ar = ar
        self.r = r

        self.add_trigger(self.ar)
        self.add_trigger(self.r)

    def interrupt(self):
        self.ar.interrupt()
        self.r.interrupt()

    @classmethod
    def from_dut(
        cls: Type[T],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        dtype: Type = int,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs
    ) -> T:
        prefix = "" if prefix is None else f"{prefix}_"
        return cls(
            ar=MasterChannelDriver.from_dut(
                dut, f"{prefix}ar", f"addr", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            r=SlaveChannelDriver.from_dut(
                dut, f"{prefix}r", f"data", index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            *args,
            **kwargs
        )


class MasterAxiDriver(Driver):
    def __init__(
        self,
        clk: SimHandleBase,
        strb: SimHandleBase,
        write: Optional[MasterWriteAxiDriver] = None,
        read: Optional[MasterReadAxiDriver] = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.clk = clk
        self.strb = strb
        self.axi_write = write
        self.axi_read = read

        self.write_done = 0

        if self.axi_write is not None:
            self.add_trigger(self.axi_write)

        if self.axi_read is not None:
            self.add_trigger(self.axi_read)

    def interrupt(self):
        if self.axi_write is not None:
            self.axi_write.interrupt()

        if self.axi_read is not None:
            self.axi_read.interrupt()

        super().interrupt()

    async def write(
        self,
        data: Union[int, List[int]] = None,
        addr: Union[int, List[int]] = None,
        strb: Union[int, List[int]] = None
        ) -> None:

        async def send_addr():
            if addr is not None:
                if isinstance(addr, int):
                    await self.axi_write.aw.push(addr)
                else:
                    for elem in addr:
                        await self.axi_write.aw.push(elem)

        async def send_data():
            if data is not None and strb is None:
                if isinstance(data, int):
                    await self.axi_write.w.push(data)
                else:
                    for elem in data:
                        await self.axi_write.w.push(elem)
                        await until(self.clk, lambda: self.w_nelem == 0)
                        self.write_done += 1
            elif data is not None and strb is not None:
                if isinstance(strb, int):
                    self.strb.value = strb
                else:
                    if isinstance(data, int):
                        assert False, f'If strb is a list data must be a list too'
                    else:
                        assert len(data) == len(strb), \
                            f'strb and data must have the same amount of element : {len(data)} != {len(strb)}'

                if isinstance(data, int):
                    await self.axi_write.w.push(data)
                    await until(self.clk, lambda: self.w_nelem == 0)
                    self.write_done += 1
                elif isinstance(strb, List):
                    for elem_data, elem_strb in zip(data, strb):
                        self.strb.value = elem_strb
                        await self.axi_write.w.push(elem_data)
                        await until(self.clk, lambda: self.w_nelem == 0)
                        self.write_done += 1
                else:
                    for elem in data:
                        await self.axi_write.w.push(elem)

        task_addr = start_soon(send_addr())
        task_data = start_soon(send_data())

        await task_addr
        await task_data

    async def read(self, addr: Union[int, List[int]] = None) -> None:
        num = np.random.randint(0, 10)
        if addr is not None:
            if isinstance(addr, int):
                # while np.random.randint(0, 10) != 0 or self.write_done == 0:
                #         await RisingEdge(self.clk)
                await self.axi_read.ar.push(addr)
                self.write_done -= 1
            else:
                for elem in addr:
                    # while np.random.randint(0, 10) != 0 or self.write_done == 0:
                    #     await RisingEdge(self.clk)
                    await self.axi_read.ar.push(elem)
                    self.write_done -= 1

    async def get_read_elem(self, nb_elem: int = None) -> List[int]:
        data = []
        if nb_elem is None:
            while not self.axi_read.r.empty():
                data.append(int(await self.axi_read.r.pop()))
        else:
            for _ in range(nb_elem):
                if self.axi_read.r.empty():
                    return data
                else:
                    data.append(int(await self.axi_read.r.pop()))

        return data

    @property
    def aw_nelem(self) -> int:
        return len(self.axi_write.aw.queue)

    @property
    def w_nelem(self) -> int:
        return len(self.axi_write.w.queue)

    @property
    def ar_nelem(self) -> int:
        return len(self.axi_read.ar.queue)

    @property
    def r_nelem(self) -> int:
        return len(self.axi_read.r.queue)

    @classmethod
    def from_dut(
        cls: Type[T],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        dtype: Type = int,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs
    ) -> T:

        strb = getattr(dut, f'{prefix}_wstrb_i')
        clk = getattr(dut, 'clk_i')

        return cls(
            write=MasterWriteAxiDriver.from_dut(
                dut, prefix, index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            read=MasterReadAxiDriver.from_dut(
                dut, prefix, index,
                dtype=dtype,
                jitter=jitter,
                capacity=capacity
            ),
            strb = strb,
            clk= clk,
            *args,
            **kwargs
        )
