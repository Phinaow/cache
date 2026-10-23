import pytest
from cocotb_tools.runner import get_runner
from pathlib import Path

@pytest.fixture
def runner(request):

    sources = [
        "cache_pkg.sv",
        "refill_engine.sv",
        "writeback_engine.sv",
        "cdc_handshake.sv",
        "miss_handler.sv",
        "plru.sv",
        "cache_controller.sv",
        "hit_detection.sv",
        "transaction.sv",
        "bl_mem.sv",
        "true_dual_port_ram.sv",
        "reset_sync.sv",
        "cache_core.sv",
    ]

    rtl_path = (Path(__file__) / "../../src").resolve()
    uart_rtl_path = rtl_path / "uart"
    sources = [rtl_path / src for src in sources]

    # Each test module builds its own DUT; keep the existing simulator/options.
    top = request.module.__name__.split(".")[-1].removeprefix("test_")
    if top == "geometry":
        top = "cache_core"
    options = getattr(request, "param", {})
    parameters = {key: value for key, value in options.items() if not key.startswith("CACHE_")}
    defines = {key: value for key, value in options.items() if key.startswith("CACHE_")}
    configuration = "_".join(f"{key}_{value}" for key, value in sorted(options.items()))
    build_name = f"{top}_{configuration}" if configuration else top
    if top == "struct_access":
        sources.append(Path(__file__).parent / "rtl" / "struct_access.sv")
    if top == "top_cache":
        sources += [rtl_path / "top_cache.sv", Path(__file__).parent / "rtl" / "adam_mig_model.sv"]
        parameters = {"USE_VENDOR_RAM": 0}
    if top in ("fifo", "r_buffer", "t_buffer", "uart_rx", "uart_tx", "data_to_axi"):
        sources.append(uart_rtl_path / f"{top}.sv")
    if top in ("uart_to_axi", "top_uart"):
        uart_modules = ["uart_rx", "uart_tx", "r_buffer", "t_buffer", "fifo", "data_to_axi", top]
        sources += [uart_rtl_path / f"{name}.sv" for name in uart_modules]
    if top == "uart_to_cache":
        uart_modules = ["uart_rx", "uart_tx", "r_buffer", "t_buffer", "data_to_axi", "uart_to_axi", "uart_to_cache"]
        sources += [uart_rtl_path / f"{name}.sv" for name in uart_modules]
        sources += [rtl_path / "top_cache.sv", Path(__file__).parent / "rtl" / "adam_mig_model.sv",
                    Path(__file__).parent / "rtl" / "clk_ref_mig_model.sv"]

    runner = get_runner("verilator")
    runner.build(
        sources=sources,
        hdl_toplevel=top,
        build_dir=rtl_path.parent / "sim_build" / "tests" / build_name,
        parameters=parameters,
        defines=defines,
        build_args = [
            "--assert",
            "--trace-vcd",
            "--trace-structs",
            "-Wno-MULTIDRIVEN",
            "-CFLAGS", "-DVM_TRACE=1",
            "-CFLAGS", "-DVM_TRACE_VCD=1"
        ]
        )
    return runner
