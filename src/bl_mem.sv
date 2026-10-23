// Asymmetric dual-clock RAM. Port A is the narrow port, port B the wide port.
// Each byte bank has exactly one read/write port per clock, allowing BRAM
// inference. A registered bank selection preserves synchronous READ_FIRST.
module bl_mem #(
    parameter int BYTE_WIDTH = 8,
    parameter int PORTA_BYTES = 4,
    parameter int PORTB_BYTES = 16,
    parameter int PORTA_DEPTH = 2048,
    localparam int PORTA_WIDTH = PORTA_BYTES * BYTE_WIDTH,
    localparam int PORTB_WIDTH = PORTB_BYTES * BYTE_WIDTH,
    localparam int PORTA_ADDR_W = PORTA_DEPTH > 1 ? $clog2(PORTA_DEPTH) : 1,
    localparam int PORTB_DEPTH = PORTA_DEPTH * PORTA_BYTES / PORTB_BYTES,
    localparam int PORTB_ADDR_W = PORTB_DEPTH > 1 ? $clog2(PORTB_DEPTH) : 1
) (
    input logic clk_a,
    input logic en_a,
    input logic [PORTA_BYTES-1:0] strb_a,
    input logic [PORTA_ADDR_W-1:0] addr_a,
    input logic [PORTA_WIDTH-1:0] wdata_a,
    output logic [PORTA_WIDTH-1:0] rdata_a,
    input logic clk_b,
    input logic en_b,
    input logic [PORTB_BYTES-1:0] strb_b,
    input logic [PORTB_ADDR_W-1:0] addr_b,
    input logic [PORTB_WIDTH-1:0] wdata_b,
    output logic [PORTB_WIDTH-1:0] rdata_b
);
  localparam int RATIO = PORTB_BYTES / PORTA_BYTES;
  localparam int SELECT_W = RATIO > 1 ? $clog2(RATIO) : 1;
  logic [SELECT_W-1:0] selection_q;
  logic [PORTB_ADDR_W-1:0] row_a;
  logic [BYTE_WIDTH-1:0] narrow_data_q [PORTB_BYTES];

  // Keep the index unsigned: a sized cast of an int is otherwise signed and
  // the upper half of the array becomes a negative index in 4-state simulators.
  assign row_a = PORTB_ADDR_W'(int'(addr_a) / RATIO);

  initial begin
    assert (PORTA_BYTES > 0 && PORTB_BYTES >= PORTA_BYTES &&
            PORTB_BYTES % PORTA_BYTES == 0 && (RATIO & (RATIO - 1)) == 0 &&
            PORTA_DEPTH >= RATIO && PORTA_DEPTH % RATIO == 0)
      else $fatal(1, "RAM requires an integral power-of-two wide/narrow ratio");
  end

  always_ff @(posedge clk_a) begin
    if (en_a) selection_q <= SELECT_W'(int'(addr_a) % RATIO);
  end

  for (genvar bank = 0; bank < PORTB_BYTES; bank++) begin : banks
    (* ram_style = "block" *) logic [BYTE_WIDTH-1:0] memory [PORTB_DEPTH];
    always_ff @(posedge clk_a) begin
      if (en_a && int'(addr_a) % RATIO == bank / PORTA_BYTES) begin
        narrow_data_q[bank] <= memory[row_a];
        if (strb_a[bank % PORTA_BYTES])
          memory[row_a] <=
            wdata_a[(bank % PORTA_BYTES)*BYTE_WIDTH +: BYTE_WIDTH];
      end
    end
    always_ff @(posedge clk_b) begin
      if (en_b) begin
        rdata_b[bank*BYTE_WIDTH +: BYTE_WIDTH] <= memory[addr_b];
        if (strb_b[bank]) memory[addr_b] <= wdata_b[bank*BYTE_WIDTH +: BYTE_WIDTH];
      end
    end
  end

  for (genvar byte_index = 0; byte_index < PORTA_BYTES; byte_index++) begin : narrow_output
    assign rdata_a[byte_index*BYTE_WIDTH +: BYTE_WIDTH] =
      narrow_data_q[int'(selection_q) * PORTA_BYTES + byte_index];
  end
endmodule
