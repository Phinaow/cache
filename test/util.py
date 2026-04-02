from cocotb.handle import SimHandleBase
from cocotb.triggers import RisingEdge, Timer
from dataclasses import asdict, is_dataclass
from numpy.typing import NDArray
from typing import Any, Callable, TypeVar, get_origin, get_args
import cocotb
import numpy as np
import re

T = TypeVar("T")


def clog2(x: int) -> int:
    if x <= 0:
        raise ValueError("clog2 is only defined for positive integers")
    return (x - 1).bit_length()


def cdiv(a: int, b: int) -> int:
    return (a + b - 1) // b


def ones_mask(x: int) -> int:
    return (1 << x) - 1


async def gen_clk(clk: SimHandleBase) -> None:
    while True:
        clk.value = 1
        await Timer(10, units="ns")
        clk.value = 0
        await Timer(10, units="ns")


async def gen_rst(clk: SimHandleBase, rst: SimHandleBase) -> None:
    rst.value = 1
    for _ in range(5):
        await RisingEdge(clk)

    rst.value = 0


async def gen_clk_rst(clk: SimHandleBase, rst: SimHandleBase) -> None:
    await cocotb.start(gen_clk(clk))
    await cocotb.start(gen_rst(clk, rst))


async def cycles(clk: SimHandleBase, n: int) -> None:
    for _ in range(n):
        await RisingEdge(clk)


async def cycles_timeout(clk: SimHandleBase, count: int) -> None:
    await cycles(clk, count)
    assert False


async def until(clk: SimHandleBase, func: Callable[[], bool]):
    while True:
        await RisingEdge(clk)
        if func():
            break


def set_value(handle: SimHandleBase, value: Any) -> None:
    if is_dataclass(value):
        set_value(handle, asdict(value))

    elif isinstance(value, dict):
        for k, v in value.items():
            set_value(getattr(handle, k), v)

    elif isinstance(value, (tuple, list, np.ndarray)):
        for i, v in enumerate(value):
            set_value(handle[i], v)

    elif (
        isinstance(value, np.generic) and
        np.issubdtype(value.dtype, np.integer)
    ):
        set_value(handle, int(value))

    elif isinstance(value, (bool, int)):
        assert value >= 0
        handle.value = value

    else:
        raise TypeError(f"Invalid type: {type(value)}")


def get_value(handle: SimHandleBase, dtype: type[T]) -> T:
    args = get_args(dtype)
    origin = get_origin(dtype)
    dtype = origin if origin else dtype

    if is_dataclass(dtype):
        kwargs = {}
        for attr, attr_dtype in dtype.__annotations__.items():
            attr_handle = getattr(handle, attr)
            kwargs[attr] = get_value(attr_handle, attr_dtype)

        return dtype(**kwargs)

    elif issubclass(np.ndarray, dtype):
        _, dtype = args
        dtype = get_args(dtype)[0]
        return np.asarray(get_value(handle, list[dtype]), dtype=dtype)

    elif issubclass(np.dtype, dtype):
        actual_dtype = args[0]
        return get_value(handle, actual_dtype)

    elif issubclass(tuple, dtype):
        return tuple(
            get_value(handle[i], args[i])
            for i, _ in enumerate(handle)
        )

    elif issubclass(list, dtype):
        item_type = args[0]
        return [
            get_value(handle[i], item_type)
            for i, _ in enumerate(handle)
        ]

    else:
        return dtype(int(handle.value))


def assert_equal_value(a: Any, b: Any) -> bool:
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return np.testing.assert_equal(a, b)

    elif is_dataclass(a):
        assert_equal_value(asdict(a), asdict(b))

    elif isinstance(a, dict):
        for k in a.keys():
            assert_equal_value(a[k], b[k])

    elif isinstance(a, list) or isinstance(a, tuple):
        for i, _ in enumerate(a):
            assert_equal_value(a[i], b[i])

    else:
        assert a == b


def load_pkg_params(pkg_path: str) -> dict[str, str]:
    pattern = re.compile(r"(\w+)\s*=\s*([\w\*\-\+\^\/]+);")
    params = {}

    with open(pkg_path, "r") as file:
        for line in file:
            match = pattern.search(line)
            if match:
                key = match.group(1)
                value = match.group(2)
                params[key] = value

    return params


def random_array(*args: int, dtype: np.dtype) -> NDArray:
    if np.issubdtype(dtype, np.unsignedinteger):
        return np.random.randint(0, 10, size=args, dtype=dtype)
    elif np.issubdtype(dtype, np.signedinteger):
        return np.random.randint(-5, 5, size=args, dtype=dtype)
    elif np.issubdtype(dtype, np.floating):
        return np.random.rand(*args).astype(dtype)
    else:
        raise ValueError()
