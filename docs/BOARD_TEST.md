# Nexys Video Validation

The physical build uses the real MIG and clock wizard IPs. `USE_VENDOR_RAM` selects `1` for Block Memory Generator or `0` for RTL RAM inferred as BRAM. Models under `test/rtl` are for simulation only.

## Build and check

```bash
vivado -mode batch -source scripts/build_fpga.tcl -tclargs ip impl
vivado -mode batch -source scripts/build_fpga.tcl -tclargs rtl impl
python3 scripts/check_fpga_reports.py sim_build/vivado/fpga_ip sim_build/vivado/fpga_rtl
```

Run these commands from the repository root with Vivado in `PATH`. `resume_fpga.tcl` resumes an existing project after an RTL change. The report checker rejects negative timing, failing endpoints, critical CDC/DRC findings, missing skew constraints, and truncated bitstreams. It also prints the bitstream SHA-256.

## Program and test

Connect PROG/JTAG and UART, power the board, release reset, and start `hw_server`. Then run:

```bash
vivado -mode batch -source scripts/program_board.tcl -tclargs sim_build/vivado/fpga_ip/cache_fpga.runs/impl_1/uart_to_cache.bit
python3 scripts/test_board.py /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A904CZUE-if00-port0 --backend ip --output sim_build/vivado/board_ip.json
```

The JTAG script targets board identifier `210276B063C4` and requires exactly one xc7a200t FPGA. Update the identifier explicitly for another board. Programming is volatile and never writes flash. The Python test requires `pyserial` and uses 115200 baud, 8N1, without flow control.

The test **overwrites data** at eight words in each of the first 32 1 KiB lines, plus `0x1FFFFC00` and `0x1FFFFFFC`. It initializes and compares 258 words, forces dirty evictions, runs 1,000 reproducible random operations, checks ERR! responses for forbidden addresses, and rereads all legal data. Repeat with the `fpga_rtl` bitstream, `--backend rtl`, and another result file.

Commands are sequential. A missing or inconsistent response stops the campaign. Successful DDR accesses verify integrated operation after calibration, but the protocol exposes neither calibration telemetry nor precise cache latency. Host/UART latency must not be interpreted as hit or miss latency.
