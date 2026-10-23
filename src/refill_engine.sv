module refill_engine
  import cache_pkg::*;
(
    input logic clk_i,
    input logic rst_ni,
    // The caller keeps VALID asserted until completion, not just acceptance.
    input cdc_data_t data_i,
    input logic addr_valid_i,
    output logic addr_ready_o,
    output logic [1:0] status_o,
    output logic [MEM_CACHE_ADDR_W-1:0] ram_addr_o,
    output logic [MEM_DATA_W-1:0] ram_data_o,
    output logic [MEM_DATA_W/8-1:0] ram_we_o,
    output logic [MEM_ADDR_W-1:0] axi_araddr_o,
    output logic [7:0] axi_arlen_o,
    output logic [2:0] axi_arsize_o,
    output logic [1:0] axi_arburst_o,
    output logic axi_arvalid_o,
    input logic axi_arready_i,
    input logic [MEM_DATA_W-1:0] axi_rdata_i,
    input logic [1:0] axi_rresp_i,
    input logic axi_rlast_i,
    input logic axi_rvalid_i,
    output logic axi_rready_o
);
  typedef enum logic [1:0] {Idle, Address, Data, Drain} state_t;
  state_t state_q;
  cdc_data_t command_q;
  logic [8:0] beat_q;
  logic error_q;
  logic expected_last, beat_error;

  assign expected_last = beat_q == {1'b0, command_q.nb_transfer};
  assign beat_error = axi_rresp_i != AXI_OKAY || (axi_rlast_i != expected_last);
  assign status_o = error_q || (axi_rvalid_i && axi_rready_o && beat_error)
                    ? AXI_SLVERR : AXI_OKAY;
  assign axi_araddr_o = command_q.mem_addr;
  assign axi_arlen_o = command_q.nb_transfer;
  assign axi_arsize_o = 3'($clog2(MEM_DATA_W / 8));
  assign axi_arburst_o = 2'b01;
  assign axi_arvalid_o = rst_ni && state_q == Address;
  assign axi_rready_o = rst_ni && (state_q == Data || state_q == Drain);
  assign ram_addr_o = command_q.cache_addr + MEM_CACHE_ADDR_W'(beat_q);
  assign ram_data_o = axi_rdata_i;
  assign ram_we_o = (state_q == Data && axi_rvalid_i &&
                     axi_rresp_i == AXI_OKAY) ? '1 : '0;
  assign addr_ready_o = rst_ni && axi_rvalid_i && axi_rready_o && axi_rlast_i;

  always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
      state_q <= Idle;
      command_q <= '0;
      beat_q <= '0;
      error_q <= 1'b0;
    end else begin
      case (state_q)
        Idle: if (addr_valid_i && data_i.wb_rf == REFILL) begin
          command_q <= data_i;
          beat_q <= '0;
          error_q <= 1'b0;
          state_q <= Address;
        end
        Address: if (axi_arready_i) state_q <= Data;
        Data: if (axi_rvalid_i) begin
          error_q <= error_q || beat_error;
          if (axi_rlast_i) state_q <= Idle;
          else if (expected_last) state_q <= Drain;
          else beat_q <= beat_q + 1'b1;
        end
        // An overlong response is drained without writing outside the line.
        Drain: if (axi_rvalid_i && axi_rlast_i) state_q <= Idle;
        default: state_q <= Idle;
      endcase
    end
  end
endmodule
