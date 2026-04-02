from __future__ import annotations
from abc import abstractmethod
from cocotb.triggers import Combine, Waitable
from cocotb.handle import SimHandleBase
from typing import Optional, List, TypeVar, Type

T = TypeVar("T")


class Driver(Waitable):
    """
    Abstract base class for cocotb drivers
    """

    @abstractmethod
    def __init__(self) -> None:
        self.interrupted = False
        self.triggers: List[Waitable] = []

    async def _wait(self) -> None:
        """
        Allows the driver to be awaited by returning its current trigger.
        """
        await Combine(*self.triggers)

    def add_trigger(self, other) -> None:
        """
        Adds a trigger to the driver's awaitable chain.
        """
        self.triggers.append(other)

    def interrupt(self) -> None:
        """
        Interrupts the driver.
        """
        self.interrupted = True

    async def stop(self) -> None:
        """
        Interrupts the driver and waits on the current trigger chain.
        """
        self.interrupt()
        await self

    @classmethod
    def from_dut(
        cls: Type[T],
        dut: SimHandleBase,
        prefix: Optional[str] = None,
        index: Optional[int] = None,
        *args,
        **kwargs
    ) -> T:
        raise NotImplementedError()
