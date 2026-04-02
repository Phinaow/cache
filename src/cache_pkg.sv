`ifndef CACHE_PKG_SV
`define CACHE_PKG_SV

package cache_pkg;

  // External memory parameters
  parameter int unsigned MEM_ADDR_W = 32;
  parameter int unsigned MEM_DATA_W = 128;
  parameter int unsigned MEM_SIZE = 512 * 2 ** 20;  // 512MB

  // CPU parameters
  parameter int unsigned CPU_DATA_W = 32;
  parameter int unsigned CPU_ADDR_W = 32;

  // Cache parameters

  // Number of words in the cache seen by the cpu
  parameter int unsigned CPU_CACHE_SIZE = 512;
  // Number of words in the cache seen by the memory
  parameter int unsigned MEM_CACHE_SIZE = (CPU_CACHE_SIZE * CPU_ADDR_W) / MEM_DATA_W;

  parameter int unsigned CPU_CACHE_ADDR_W = $clog2(CPU_CACHE_SIZE);
  parameter int unsigned MEM_CACHE_ADDR_W = $clog2(MEM_CACHE_SIZE);

  parameter int unsigned CACHE_SIZE = CPU_CACHE_SIZE * CPU_DATA_W / 8;
  parameter int unsigned NB_LINE = 4;
  parameter int unsigned NB_TAG = $clog2(NB_LINE);
  parameter int unsigned LINE_SIZE = CACHE_SIZE / NB_LINE;

  parameter int unsigned OFFSET_SIZE = $clog2(CPU_DATA_W / 8);
  parameter int unsigned WORD_SIZE = $clog2(LINE_SIZE) - OFFSET_SIZE;
  parameter int unsigned TAG_SIZE = $clog2(MEM_SIZE) - WORD_SIZE - OFFSET_SIZE;

  parameter int unsigned OFFSET_POS = $clog2(CPU_DATA_W / 8);
  parameter int unsigned WORD_POS = $clog2(LINE_SIZE);
  parameter int unsigned TAG_POS = $clog2(MEM_SIZE);
  parameter int unsigned OVERFLOW = CPU_ADDR_W - TAG_POS;

  typedef struct packed {
    logic [MEM_ADDR_W-1:0] mem_addr;
    logic [7:0] nb_transfer;
    logic [MEM_CACHE_ADDR_W-1:0] cache_addr;
  } cache_op_t;

  typedef enum logic {
    REFILL = 1'b0,
    WRITEBACK = 1'b1
  } rf_wb_e;

  typedef struct packed {
    logic [MEM_ADDR_W-1:0] mem_addr;
    logic [7:0] nb_transfer;
    logic [MEM_CACHE_ADDR_W-1:0] cache_addr;
    rf_wb_e wb_rf;
  } cdc_data_t;

endpackage

`endif
