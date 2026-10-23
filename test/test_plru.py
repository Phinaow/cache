"""Tree-PLRU: compare every accepted access with an independent reference."""
import random
import os

import pytest

import cocotb
from cocotb.triggers import Timer


class PlruModel:
    def __init__(self, ways):
        self.ways = ways
        self.tree = [0] * (ways - 1)

    def access(self, way):
        # Find the subtree containing the accessed way, then point away from it.
        node = 0
        first = 0
        count = self.ways
        while count > 1:
            count //= 2
            right = way >= first + count
            self.tree[node] = int(not right)
            node = 2 * node + 1 + int(right)
            if right:
                first += count

    def victim(self):
        node = 0
        first = 0
        count = self.ways
        while count > 1:
            count //= 2
            right = self.tree[node]
            node = 2 * node + 1 + right
            first += count * right
        return first


async def cycle(dut, way=0, valid=False, reset=False):
    dut.clk_i.value = 0
    dut.rst_ni.value = int(not reset)
    dut.access_i.value = way
    dut.access_valid_i.value = int(valid)
    await Timer(5, unit="ns")
    accepted = bool(dut.access_ready_o.value) and valid
    dut.clk_i.value = 1
    await Timer(5, unit="ns")
    return accepted


@cocotb.test()
async def reference_model_and_back_to_back_accesses(dut):
    ways = int(os.environ["TEST_WAYS"])
    model = PlruModel(ways)
    await cycle(dut, reset=True)
    assert int(dut.lru_way_o.value) == 0
    rng = random.Random(0x1A2B)
    accessed = set()
    victims = set()

    # Directed sequences followed by a full-rate random stream and idle gaps.
    sequence = list(range(ways)) * 3 + [0] * 10
    sequence += [rng.randrange(ways) for _ in range(2000)]
    for index, way in enumerate(sequence):
        valid = index < 3 * ways or rng.randrange(5) != 0
        accepted = await cycle(dut, way, valid)
        assert accepted == valid, "The simple tree must accept one access per cycle"
        if accepted:
            model.access(way)
            accessed.add(way)
        assert dut.lru_way_valid_o.value == 1
        victim = int(dut.lru_way_o.value)
        assert victim == model.victim(), f"way={way}, step={index}: victim={victim}, tree={model.tree}"
        victims.add(victim)
    assert accessed == set(range(ways))
    assert victims == set(range(ways))

    # A second reset must clear an already-used tree.
    await cycle(dut, reset=True)
    assert dut.access_ready_o.value == 0
    assert dut.lru_way_valid_o.value == 0
    await cycle(dut)
    assert dut.lru_way_o.value == 0


@pytest.mark.parametrize("runner", [{"WAYS": ways} for ways in (1, 2, 4, 8, 16)], indirect=True)
def test_plru(runner):
    runner.test(hdl_toplevel="plru", test_module=__name__, test_args=["--trace"],
                extra_env={"TEST_WAYS": str(runner.parameters["WAYS"])})
