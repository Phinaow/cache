# FPGA Cache

Fully associative, write-back, write-allocate cache between an AXI-Lite processor and DDR3 memory over AXI. The reference configuration is 8 KiB, with eight 1 KiB lines, 32-bit CPU data, and 128-bit memory data.

The `cache_core` module combines the controller, tree-PLRU replacement, cache-line transfers, two CDC mailboxes, and dual-port RAM. `USE_VENDOR_RAM` selects either the RTL RAM or the Vivado IP at elaboration time. `top_cache` adds the MIG, while `uart_to_cache` provides the Nexys Video serial interface.

The cache is blocking during a miss. CPU addresses must be four-byte aligned; invalid accesses return SLVERR without side effects. Reset discards dirty lines, and the cached DDR region must be exclusively owned by this cache.

- [Project handoff](docs/PASSATION.md)
- [ADAM integration handoff](docs/ADAM_INTEGRATION_HANDOFF.md)
- [Functional contract](docs/CACHE_CONTRACT.md)
- [Module descriptions and tests](docs/MODULES.md)
- [Running tests in Docker](test/README.md)
- [Validation results and limitations](docs/VERIFICATION_STATUS.md)
- [Building and testing on Nexys Video](docs/BOARD_TEST.md)
- [Finalization plan and initial audit](docs/PLAN_FINALISATION_CACHE.md)

Code comments and docstrings are written in English. Tests use Verilator's native VPI struct fields directly and rely on small, purpose-built testbenches.

Simulation success, Vivado physical closure, and board validation are reported separately. The MIG and PLL test models are never used to generate hardware.

The `adam/` subdirectory is a separate integration of this cache into the ADAM SoC. It uses a CV32E40P in the high-speed domain and Ibex in the low-power domain, and has been validated on hardware. That campaign is distinct from the standalone `uart_to_cache` demonstrator.
