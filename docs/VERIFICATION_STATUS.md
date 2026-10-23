# Verification Status

The functional campaign covers every active RTL module and top. These results are measured evidence, not a claim of exhaustive verification.

## Consolidated results

- Docker/Cocotb 2.0.1/Verilator 5.053 devel: **44 passing pytest cases**, with RTL assertions enabled (`sim_build/resumed_regression.log`). Packed structs are accessed directly through VPI; the wrapper was removed.
- Full cache: 8 KiB/8 lines, 1 KiB/1 line, 512 bytes/2 lines, and 1 KiB/4 lines. Tests cover dirty evictions, masks, R/B errors and IDs, boundary and illegal addresses, stalled responses, and resets during AR/R/AW/W/B.
- PLRU: 1/2/4/8/16 ways. FIFO depths: 1/2/3/16/256. Buffers: 32/8, 16/4, and 8/8 bits. Three illegal cache configurations are rejected explicitly.
- RTL RAM: Artix-7 BRAM inference verified, with 16 RAMB18E1 blocks and no LUT memory. XSim equivalence against the real Block Memory Generator passed over the full capacity, including READ_FIRST behavior and both ports' masks. It exposed a signed-index defect invisible in two-state Verilator simulation.
- Synthesis, placement/routing, and bitstreams passed with real MIG and clock wizard IPs for both RAM backends. No setup, hold, or pulse-width endpoint fails; both mailbox skew constraints pass.

| Backend | Setup WNS | Hold WHS | Critical CDC | Mailbox skew slack |
|---|---:|---:|---:|---|
| IP | +0.912 ns | +0.021 ns | 0 | +8.959 / +9.123 ns |
| RTL | +0.912 ns | +0.045 ns | 0 | +9.125 / +9.298 ns |

Remaining warnings are internal to the MIG: two CDC-8 findings on reset synchronizers, BUFC-1 on DQS inputs, and REQP-1709 on the PLL buffer. No global waiver hides them. Warnings caused by asynchronously reset registers driving RAM commands were eliminated with synchronous resets, after which the regression was rerun.

Core lint reports no errors without the former waivers. Warnings remain in `sim_build/lint_core.log`: dual-clock RAM writes, a reset network used synchronously and asynchronously, intentionally unused fields/bits, and one hidden name. Simulation retains the requested `-Wno-MULTIDRIVEN`; it does not replace this review.

## Hardware validation

Both backends were programmed successively into volatile memory on the Nexys Video. Each passed **1,781 UART commands**, checking **258 words**, **1,000 random operations**, dirty evictions, and invalid addresses. The standalone campaign ended with the RTL backend loaded; flash was never written. See [BOARD_TEST.md](BOARD_TEST.md) and [VALIDATION_RESULTS.json](VALIDATION_RESULTS.json).

The board was subsequently reprogrammed with the ADAM integration. That integration passed **11 pytest cases**, routed at setup `+0.037 ns` and hold `+0.008 ns` with no critical CDC/DRC findings, and passed **1,156 board commands**, **1,000 mixed operations**, and **32,784 checked DDR bytes**. Its volatile bitstream SHA-256 is `4fae4219a27db0afe4cd4d4c3d05e6d270c3602e5f7bf3a5678e1c39499eed09`. The build still reuses a prepared bootloader ROM and Ibex sources rather than a fully fresh CMake build.

## Open limitations

- No formal proof, consolidated coverage measurement, or exhaustive multi-seed campaign.
- Four-state XSim targets RAM only; the full core uses Verilator and functional MIG/PLL models.
- No calibration telemetry, hit/miss/writeback counters, or precise latency measurements.
- No flush/invalidate or external-master coherency; reset discards dirty data.
- No power-cut test or physical DDR error injection. AXI errors and calibration loss are injected in simulation.

## Reproduction

- Tests: `scripts/test_docker.sh`.
- RAM equivalence: `scripts/create_ram_ip.tcl`, then `scripts/simulate_ram_backends.tcl`.
- Build: `scripts/build_fpga.tcl -tclargs ip|rtl impl`; resume with `resume_fpga.tcl`.
- Reports: `python3 scripts/check_fpga_reports.py sim_build/vivado/fpga_ip sim_build/vivado/fpga_rtl`.
- Board: `scripts/program_board.tcl`, then `scripts/test_board.py`.

Detailed reports and bitstreams are regenerable artifacts under `sim_build/vivado/`; sources and summarized results remain in the repository.
