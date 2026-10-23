"""Invalid geometries must stop explicitly before any cache traffic."""
from pathlib import Path
import subprocess

import cocotb
from cocotb.triggers import Timer
import pytest


@cocotb.test()
async def invalid_configuration_must_not_run(dut):
    # Let the simulator evaluate its time-zero initial assertions first.
    await Timer(1, unit="ns")
    raise AssertionError("Invalid geometry was not rejected by the RTL")


@pytest.mark.parametrize("runner", [
    {"CACHE_LINES": 3},
    {"CACHE_CPU_WORDS": 3072},
    {"CACHE_CPU_WORDS": 16384},
], indirect=True)
def test_geometry(runner):
    log = Path(runner.build_dir) / "invalid_geometry.log"
    with pytest.raises((SystemExit, subprocess.CalledProcessError)):
        runner.test(hdl_toplevel="cache_core", test_module=__name__, log_file=log)
    transcript = log.read_text()
    assert ("Unsupported cache geometry" in transcript
            or "PLRU requires a positive power-of-two way count" in transcript), transcript
