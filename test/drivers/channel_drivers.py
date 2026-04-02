from __future__ import annotations
from .driver import Driver
from cocotb.handle import SimHandleBase
from cocotb.triggers import RisingEdge
from cocotb import start_soon
from typing import Any, Generic, List, Optional, Type, TypeVar
from ..util import *
import random

T = TypeVar("T")
U = TypeVar("U")


class ChannelDriver(Driver, Generic[T]):
    """Base class for handshake-based channel drivers."""

    def __init__(
        self,
        clk: SimHandleBase,
        rst: SimHandleBase,
        data: SimHandleBase,
        valid: SimHandleBase,
        ready: SimHandleBase,
        *args,
        dtype: Type,
        jitter: int = 0,
        capacity: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            clk: Clock signal.
            rst: Reset signal.
            data: Data signal.
            valid: Valid signal.
            ready: Ready signal.
            dtype: Python type matching the data signal.
            jitter: Max random delay cycles for data transfer.
            capacity: Optional maximum queue size.
        """
        super().__init__(*args, **kwargs)
        self.clk = clk
        self.rst = rst
        self.data = data
        self.valid = valid
        self.ready = ready
        self.dtype = dtype
        self.jitter = jitter
        self.capacity = capacity

        self.queue: List[T] = []
        self.transfers = 0

        # Runs forever
        start_soon(self.assert_data_stable())

    def full(self) -> bool:
        """Check if the queue is full."""
        if self.capacity is None:
            return False
        return len(self.queue) >= self.capacity

    async def assert_data_stable(self):
        """
        Ensure that the data signal is constant while valid is asserted but
        ready is not.
        """
        await until(self.clk, lambda: self.rst.value == 0)
        while True:
            await until(self.clk, lambda: self.valid.value == 1)
            expected = get_value(self.data, self.dtype)
            while self.ready.value == 0:
                actual = get_value(self.data, self.dtype)
                assert_equal_value(actual, expected)
                await RisingEdge(self.clk)

    @classmethod
    def from_dut(
        cls: Type[U],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        direction: str = "master",
        **kwargs
    ) -> U:
        """
        Create a channel driver from a DUT (Device Under Test) by automatically
        resolving the appropriate signals (data, valid, ready) based on
        prefix and direction.

        Args:
            dut: The DUT (cocotb handle).
            prefix: An optional prefix for signal names.  If provided,
                    signals are accessed like `<prefix>_i`, `<prefix>_valid_i`,
                    etc.  Defaults to "" if not given.
            index: If not None, treats the signals as arrays and accesses
                   signals at the given index.
            direction: "master" or "slave".  Determines how to map the signals.
                       Defaults to "master".
            *args: Additional positional arguments to the constructor.
            **kwargs: Additional keyword arguments to the constructor.

        Returns:
            An instance of this driver bound to the specified DUT signals.
        """
        prefix = "" if prefix is None else f"{prefix}_"

        if direction == "master":
            data = getattr(dut, f"{prefix}i")
            valid = getattr(dut, f"{prefix}valid_i")
            ready = getattr(dut, f"{prefix}ready_o")

        elif direction == "slave":
            data = getattr(dut, f"{prefix}o")
            valid = getattr(dut, f"{prefix}valid_o")
            ready = getattr(dut, f"{prefix}ready_i")

        else:
            raise ValueError(f"Unknown direction: {direction}")

        if index is not None:
            data = data[index]
            valid = valid[index]
            ready = ready[index]

        return cls(
            clk=dut.clk_i,
            rst=dut.rst_i,
            data=data,
            valid=valid,
            ready=ready,
            *args,
            **kwargs
        )


class MasterChannelDriver(ChannelDriver[T]):
    """Driver for master side of a handshake channel."""

    def __init__(
        self,
        *args,
        default: Optional[Any] = None,
        **kwargs
    ):
        """
        Args:
            *args: Positional arguments passed to the base constructor.
            default: Value to drive when not transmitting.
            **kwargs: Keyword arguments passed to the base constructor.
        """
        super().__init__(*args, **kwargs)
        self.default = self.dtype() if default is None else default
        self.add_trigger(start_soon(self.drive()))

    async def drive(self):
        """
        Drives values from a queue onto the channel with flow control and
        optional jitter.

        Waits for reset de-assertion, then on each clock cycle, may transfer
        data if the queue is non-empty and a random jitter condition is met.
        Waits for receiver readiness before completing each transfer.
        """
        set_value(self.data, self.default)
        self.valid.value = 0
        await until(self.clk, lambda: self.rst.value == 0)
        while (not self.interrupted) or self.queue:
            num = random.randint(0, self.jitter)
            if self.queue and num == 0:
                set_value(self.data, self.queue[0])
                self.valid.value = 1
                await until(self.clk, lambda: self.ready.value == 1)
                self.queue.pop(0)
                self.transfers += 1
            else:
                set_value(self.data, self.default)
                self.valid.value = 0
                await RisingEdge(self.clk)
        set_value(self.data, self.default)
        self.valid.value = 0

    async def push(self, item: T):
        """Push a new item onto the queue."""
        if self.full():
            await RisingEdge(self.clk)
        self.queue.append(item)

    @classmethod
    def from_dut(cls: Type[U], *args, **kwargs) -> U:
        """
        Create a MasterChannelDriver bound to the given DUT signals.
        """
        return super().from_dut(*args, **kwargs, direction="master")


class SlaveChannelDriver(ChannelDriver[T]):
    """Driver for slave side of a handshake channel."""

    def __init__(self, *args, **kwargs):
        """
        Args:
            *args: Positional arguments passed to the base constructor.
            default: Value to drive when not transmitting.
            **kwargs: Keyword arguments passed to the base constructor.
        """
        super().__init__(*args, **kwargs)
        self.add_trigger(start_soon(self.drive()))

    async def drive(self):
        """
        Receives values from the channel with flow control and optional
        jitter.

        Waits for reset de-assertion, then on each clock cycle, may assert
        readiness if not full and a random jitter condition is met. Captures
        data when both valid and ready are asserted, storing it in the queue.
        """
        self.ready.value = 0
        await until(self.clk, lambda: self.rst.value == 0)
        while not self.interrupted:
            num = random.randint(0, self.jitter)
            self.ready.value = (not self.full() and num == 0)
            await RisingEdge(self.clk)
            if self.valid.value == 1 and self.ready.value == 1:
                self.queue.append(get_value(self.data, self.dtype))
                self.transfers += 1
        self.ready.value = 0

    async def pop(self) -> T:
        """Pop an item from the queue."""
        while not self.queue:
            await RisingEdge(self.clk)
        return self.queue.pop(0)

    @classmethod
    def from_dut(cls: Type[U], *args, **kwargs) -> U:
        """
        Create a SlaveChannelDriver bound to the given DUT signals.
        """
        return super().from_dut(*args, **kwargs, direction="slave")
