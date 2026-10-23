`ifndef CACHE_PKG_SV
`define CACHE_PKG_SV

// Compile-time geometry overrides are shared by every module in the design.
`ifndef CACHE_CPU_WORDS
`define CACHE_CPU_WORDS 2048
`endif
`ifndef CACHE_LINES
`define CACHE_LINES 8
`endif

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
  parameter int unsigned CPU_CACHE_SIZE = `CACHE_CPU_WORDS;
  // Number of words in the cache seen by the memory
  parameter int unsigned MEM_CACHE_SIZE = (CPU_CACHE_SIZE * CPU_DATA_W) / MEM_DATA_W;

  parameter int unsigned CPU_CACHE_ADDR_W = $clog2(CPU_CACHE_SIZE);
  parameter int unsigned MEM_CACHE_ADDR_W = $clog2(MEM_CACHE_SIZE);

  parameter int unsigned CACHE_SIZE = CPU_CACHE_SIZE * CPU_DATA_W / 8;
  parameter int unsigned NB_LINE = `CACHE_LINES;
  parameter int unsigned NB_TAG = (NB_LINE > 1) ? $clog2(NB_LINE) : 1;
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

  // Responses keep the operation identity and the memory error across the CDC.
  typedef struct packed {
    rf_wb_e wb_rf;
    logic [1:0] status;
  } cache_resp_t;

  localparam logic [1:0] AXI_OKAY = 2'b00;
  localparam logic [1:0] AXI_SLVERR = 2'b10;

endpackage

`endif
