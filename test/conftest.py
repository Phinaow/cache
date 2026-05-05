import pytest
from cocotb_tools.runner import get_runner
from pathlib import Path

@pytest.fixture(scope="session")
def runner():

    sources = [
        "cache_pkg.sv",
        "refill_engine.sv",
        "writeback_engine.sv",
        "cdc_handshake.sv",
        "miss_handler.sv",
        "plru.sv",
        "cache_controller.sv",
        "hit_detection.sv",
        "transaction.sv"
    ]

    rtl_path = (Path(__file__) / "../../src").resolve()
    sources = [rtl_path / src for src in sources]

    runner = get_runner("verilator")
    runner.build(
        sources=sources,
        hdl_toplevel="cache_controller",
        build_args = [
            "--trace-vcd",
            "--trace-structs",
            "-CFLAGS", "-DVM_TRACE=1",
            "-CFLAGS", "-DVM_TRACE_VCD=1"
        ]
        )
    return runner
