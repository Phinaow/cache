# Contract for the Current Version

The cache remains fully associative, write-back, and write-allocate. The reference configuration is 8 KiB, eight 1 KiB lines, 32-bit CPU words, and 128-bit memory beats. Size parameters are expressed in bytes or words according to their names; AxLEN always means the number of beats minus one.

The frontend accepts AW and W independently and stores their payloads. Only one cache operation executes at a time; responses do not depend on READY and remain stable until handshake. Concurrent operations are arbitrated without starvation. A response is produced only after RAM access and data availability. CPU accesses must be four-byte aligned; a misaligned address or an address outside the 512 MiB memory returns SLVERR without side effects. A zero WSTRB changes neither data nor the dirty state.

A line becomes valid only after a successful refill. A dirty eviction waits for a successful writeback before reusing RAM; an error preserves the dirty line. DDR response errors propagate to the processor. A transport violation that never completes its response requires a global reset. No finite timeout is guaranteed when the recipient does not respond.

The cached DDR memory must be owned exclusively by this cache. Hardware coherency with other masters is not provided. Reset discards dirty data; no implicit flush is guaranteed. Conservative maintenance before a software reset must be designed explicitly if that capability is added. These are documented limitations, not silent behavior.

The CDC mailbox holds one entry until acknowledgement, with two-stage synchronizers in both directions. Assertion of either reset cancels the transfer in both domains; deassertion is synchronized locally. Simulation verifies digital transfers, while Vivado CDC/RDC reports and constraints are required for physical closure.

The RAM has synchronous reads, per-byte write masks, and two clocks. An elaboration parameter selects the RTL backend or Vivado IP behind the same contract. Cross-port conflicts on common bytes are forbidden, or must be explicitly excluded from consumed data. No initial contents are assumed.

This contract defines the target behavior. Implementation tracking distinguishes corrected and tested modules from outstanding work; it does not declare the current cache compliant before integration testing.
