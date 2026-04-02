module refill_engine
  import cache_pkg::*;
(
    input logic clk_i,
    input logic rst_ni,

    input  cdc_data_t             data_i,
    input  logic                  addr_valid_i,
    output logic                  addr_ready_o,

    output logic [MEM_CACHE_ADDR_W-1:0] ram_addr_o,
    output logic [      MEM_DATA_W-1:0] ram_data_o,
    output logic [                15:0] ram_we_o,

    output logic [MEM_ADDR_W-1:0] axi_araddr_o,
    output logic [           7:0] axi_arlen_o,
    output logic [           2:0] axi_arsize_o,
    output logic [           1:0] axi_arburst_o,
    output logic                  axi_arvalid_o,
    input  logic                  axi_arready_i,

    input  logic [MEM_DATA_W-1:0] axi_rdata_i,
    input  logic                  axi_rlast_i,
    input  logic                  axi_rvalid_i,
    output logic                  axi_rready_o
);

  typedef enum {
    StIdle,
    StSendAddr,
    StReadData
  } state_e;

  state_e state_q, state_d;
  logic [MEM_CACHE_ADDR_W-1:0] write_ptr_q, write_ptr_d;

  assign axi_arlen_o   = data_i.nb_transfer; // 8'd127;
  assign axi_arsize_o  = 3'd4;
  assign axi_arburst_o = 2'b01;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q     <= StIdle;
      write_ptr_q <= 0;
    end else begin
      state_q     <= state_d;
      write_ptr_q <= write_ptr_d;
    end
  end

  always_comb begin

    axi_arvalid_o = 1'b0;
    axi_rready_o  = 1'b0;
    addr_ready_o  = 1'b0;
    write_ptr_d   = data_i.cache_addr;
    state_d       = state_q;

    unique case (state_q)
      StIdle: begin
        if (addr_valid_i && data_i.wb_rf == REFILL) begin
          state_d = StSendAddr;
        end
      end

      StSendAddr: begin
        axi_arvalid_o = 1'b1;
        if (axi_arready_i) begin
          state_d = StReadData;
        end
      end

      StReadData: begin
        axi_rready_o = 1'b1;
        write_ptr_d  = write_ptr_q;

        if (axi_rvalid_i && axi_rready_o) begin
          write_ptr_d = write_ptr_q + 1'b1;
          if (axi_rlast_i) begin
            addr_ready_o = 1'b1;
            state_d = StIdle;
          end
        end
      end

      default:;

    endcase
  end

  assign ram_addr_o   = write_ptr_q;
  assign ram_data_o   = axi_rdata_i;
  assign ram_we_o     = (axi_rvalid_i && axi_rready_o) ? '1 : '0;
  assign axi_araddr_o = data_i.mem_addr;

endmodule
