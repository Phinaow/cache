`ifndef CACHE_PKG_SV
`define CACHE_PKG_SV

package cache_pkg;

  // External memory parameters
  parameter int unsigned MEM_ADDR_W = 32;
  parameter int unsigned MEM_DATA_W = 128;

  // CPU parameters
  parameter int unsigned CPU_DATA_W = 32;
  parameter int unsigned CPU_ADDR_W = 32;

  // Cache parameters
  parameter int unsigned CPU_CACHE_SIZE = 512;  // Number of words in the cache seen by the cpu
  parameter int unsigned MEM_CACHE_SIZE = 128;  // Number of words in the cache seen by the memory
  parameter int unsigned CPU_CACHE_ADDR_W = $clog2(CPU_CACHE_SIZE);
  parameter int unsigned MEM_CACHE_ADDR_W = $clog2(MEM_CACHE_SIZE);

endpackage

`endif
