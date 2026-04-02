module writeback_engine
  import cache_pkg::*;
(
    input logic clk_i,
    input logic rst_ni,

    input  cdc_data_t             data_i,
    input  logic                  addr_valid_i,
    output logic                  addr_ready_o,

    output logic [MEM_CACHE_ADDR_W-1:0] ram_addr_o,
    input  logic [      MEM_DATA_W-1:0] ram_data_i,

    output logic [MEM_ADDR_W-1:0] axi_awaddr_o,
    output logic [           7:0] axi_awlen_o,
    output logic [           2:0] axi_awsize_o,
    output logic [           1:0] axi_awburst_o,
    output logic                  axi_awvalid_o,
    input  logic                  axi_awready_i,

    output logic [  MEM_DATA_W-1:0] axi_wdata_o,
    output logic [MEM_DATA_W/8-1:0] axi_wstrb_o,
    output logic                    axi_wlast_o,
    output logic                    axi_wvalid_o,
    input  logic                    axi_wready_i,

    input  logic [1:0] axi_bresp_i,
    input  logic       axi_bvalid_i,
    output logic       axi_bready_o
);

  typedef enum {
    StIdle,
    StSendAW,
    StWriteData,
    StWaitBresp
  } state_e;

  state_e state_q, state_d;
  logic [MEM_CACHE_ADDR_W:0] read_ptr_q, read_ptr_d;

  logic [MEM_DATA_W-1:0] data_buffer;

  logic sample_data;

  assign axi_awlen_o   = data_i.nb_transfer; // 8'd127;
  assign axi_awsize_o  = 3'd4;
  assign axi_awburst_o = 2'b01;
  assign axi_wstrb_o   = '1;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q     <= StIdle;
      read_ptr_q  <= '0;
      data_buffer <= '0;
    end else begin
      state_q    <= state_d;
      read_ptr_q <= read_ptr_d;

      if (sample_data) begin
        data_buffer <= ram_data_i;
      end

    end
  end

  assign sample_data = axi_wvalid_o && axi_wready_i ||
          read_ptr_d[MEM_CACHE_ADDR_W-1:0] == data_i.cache_addr;

  always_comb begin

    axi_awvalid_o = 1'b0;
    axi_wlast_o   = 1'b0;
    axi_wvalid_o  = 1'b0;
    axi_bready_o  = 1'b0;
    addr_ready_o  = 1'b0;
    read_ptr_d[MEM_CACHE_ADDR_W-1:0]    = data_i.cache_addr;
    state_d       = state_q;

    unique case (state_q)
      StIdle: begin
        if (addr_valid_i && data_i.wb_rf == WRITEBACK) begin
          state_d = StSendAW;
        end
      end

      StSendAW: begin
        axi_awvalid_o = 1'b1;
        if (axi_awready_i) begin
          state_d = StWriteData;
        end
      end

      StWriteData: begin

        read_ptr_d = read_ptr_q;

        if (read_ptr_q[MEM_CACHE_ADDR_W-1:0] > data_i.cache_addr &&
          read_ptr_q <= data_i.nb_transfer + data_i.cache_addr) begin
          axi_wvalid_o = 1'b1;
        end

        if (read_ptr_q[MEM_CACHE_ADDR_W-1:0] == data_i.cache_addr) begin
          read_ptr_d = read_ptr_q + 1'b1;
        end else if (axi_wready_i) begin

          if (read_ptr_q == data_i.nb_transfer + data_i.cache_addr) begin
            axi_wlast_o = 1'b1;
            state_d     = StWaitBresp;
          end else begin
            read_ptr_d = read_ptr_q + 1'b1;
          end
        end

      end

      StWaitBresp: begin
        axi_bready_o = 1'b1;
        if (axi_bvalid_i) begin
          addr_ready_o = 1'b1;
          state_d = StIdle;
        end
      end

      default:;
    endcase
  end

  assign ram_addr_o   = read_ptr_d[MEM_CACHE_ADDR_W-1:0];
  assign axi_wdata_o  = data_buffer;
  assign axi_awaddr_o = data_i.mem_addr;

endmodule
