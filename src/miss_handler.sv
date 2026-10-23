module miss_handler
  import cache_pkg::*;
(
    // ----------------------- //
    // Clock and reset signals
    // ----------------------- //
    input  logic                             clk_i,
    input  logic                             rst_ni,
    // Control signals
    input  cdc_data_t                        cdc_data_i,
    input  logic                             cdc_valid_i,
    output logic                             cdc_ready_o,

    output cache_resp_t resp_data_o,
    output logic resp_valid_o,
    input logic resp_ready_i,
    // ----------- //
    // RAM signals
    // ----------- //
    // Addr
    output logic      [MEM_CACHE_ADDR_W-1:0] ram_addr_o,
    output logic ram_en_o,
    input  logic      [      MEM_DATA_W-1:0] ram_data_i,
    output logic      [      MEM_DATA_W-1:0] ram_data_o,
    output logic      [  (MEM_DATA_W/8)-1:0] ram_we_o,
    // ----------------- //
    // Write AXI signals
    // ----------------- //
    // Config signals
    output logic      [                 1:0] m_axi_awid,
    output logic      [      MEM_ADDR_W-1:0] m_axi_awaddr,
    output logic      [                 7:0] m_axi_awlen,
    output logic      [                 2:0] m_axi_awsize,
    output logic      [                 1:0] m_axi_awburst,
    output logic      [                 0:0] m_axi_awlock,
    output logic      [                 3:0] m_axi_awcache,
    output logic      [                 2:0] m_axi_awprot,
    output logic      [                 3:0] m_axi_awqos,
    output logic                             m_axi_awvalid,
    input  logic                             m_axi_awready,
    // Data signals
    output logic      [      MEM_DATA_W-1:0] m_axi_wdata,
    output logic      [    MEM_DATA_W/8-1:0] m_axi_wstrb,
    output logic                             m_axi_wlast,
    output logic                             m_axi_wvalid,
    input  logic                             m_axi_wready,
    // Response signals
    input  logic      [                 1:0] m_axi_bid,
    input  logic      [                 1:0] m_axi_bresp,
    input  logic                             m_axi_bvalid,
    output logic                             m_axi_bready,
    // ---------------- //
    // Read AXI signals
    // ---------------- //
    // Config signals
    output logic      [                 1:0] m_axi_arid,
    output logic      [      MEM_ADDR_W-1:0] m_axi_araddr,
    output logic      [                 7:0] m_axi_arlen,
    output logic      [                 2:0] m_axi_arsize,
    output logic      [                 1:0] m_axi_arburst,
    output logic      [                 0:0] m_axi_arlock,
    output logic      [                 3:0] m_axi_arcache,
    output logic      [                 2:0] m_axi_arprot,
    output logic      [                 3:0] m_axi_arqos,
    output logic                             m_axi_arvalid,
    input  logic                             m_axi_arready,
    // Data signals
    input  logic      [                 1:0] m_axi_rid,
    input  logic      [      MEM_DATA_W-1:0] m_axi_rdata,
    input  logic      [                 1:0] m_axi_rresp,
    input  logic                             m_axi_rlast,
    input  logic                             m_axi_rvalid,
    output logic                             m_axi_rready
);

  typedef enum logic [1:0] {Idle, Active, Response} state_t;
  state_t state_q;
  cdc_data_t command_q;
  cache_resp_t response_q;
  logic refill_done, writeback_done;
  logic [1:0] refill_status, writeback_status;
  logic [MEM_CACHE_ADDR_W-1:0] refill_address, writeback_address;

  assign cdc_ready_o = rst_ni && state_q == Idle;
  assign resp_valid_o = rst_ni && state_q == Response;
  assign resp_data_o = response_q;
  assign ram_en_o = state_q == Active;
  assign ram_addr_o = command_q.wb_rf == REFILL ? refill_address : writeback_address;

  // This cache issues one memory transaction at a time, always with ID zero.
  assign m_axi_awid = '0;
  assign m_axi_awlock = '0;
  assign m_axi_awcache = '0;
  assign m_axi_awprot = '0;
  assign m_axi_awqos = '0;
  assign m_axi_arid = '0;
  assign m_axi_arlock = '0;
  assign m_axi_arcache = '0;
  assign m_axi_arprot = '0;
  assign m_axi_arqos = '0;

  always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
      state_q <= Idle;
      command_q <= '0;
      response_q <= '0;
    end else begin
      case (state_q)
        Idle: if (cdc_valid_i && cdc_ready_o) begin
          command_q <= cdc_data_i;
          state_q <= Active;
        end
        Active: if (refill_done || writeback_done) begin
          response_q.wb_rf <= command_q.wb_rf;
          response_q.status <= command_q.wb_rf == REFILL ? refill_status : writeback_status;
          state_q <= Response;
        end
        Response: if (resp_ready_i) state_q <= Idle;
        default: state_q <= Idle;
      endcase
    end
  end

  refill_engine refill_engine_inst (
      .clk_i(clk_i), .rst_ni(rst_ni), .data_i(command_q),
      .addr_valid_i(state_q == Active && command_q.wb_rf == REFILL),
      .addr_ready_o(refill_done), .status_o(refill_status),
      .ram_addr_o(refill_address), .ram_data_o(ram_data_o), .ram_we_o(ram_we_o),
      .axi_araddr_o(m_axi_araddr), .axi_arlen_o(m_axi_arlen),
      .axi_arsize_o(m_axi_arsize), .axi_arburst_o(m_axi_arburst),
      .axi_arvalid_o(m_axi_arvalid), .axi_arready_i(m_axi_arready),
      .axi_rdata_i(m_axi_rdata),
      .axi_rresp_i((m_axi_rid == 0) ? m_axi_rresp : AXI_SLVERR),
      .axi_rlast_i(m_axi_rlast), .axi_rvalid_i(m_axi_rvalid),
      .axi_rready_o(m_axi_rready)
  );

  writeback_engine writeback_engine_inst (
      .clk_i(clk_i), .rst_ni(rst_ni), .data_i(command_q),
      .addr_valid_i(state_q == Active && command_q.wb_rf == WRITEBACK),
      .addr_ready_o(writeback_done), .status_o(writeback_status),
      .ram_addr_o(writeback_address), .ram_data_i(ram_data_i),
      .axi_awaddr_o(m_axi_awaddr), .axi_awlen_o(m_axi_awlen),
      .axi_awsize_o(m_axi_awsize), .axi_awburst_o(m_axi_awburst),
      .axi_awvalid_o(m_axi_awvalid), .axi_awready_i(m_axi_awready),
      .axi_wdata_o(m_axi_wdata), .axi_wstrb_o(m_axi_wstrb), .axi_wlast_o(m_axi_wlast),
      .axi_wvalid_o(m_axi_wvalid), .axi_wready_i(m_axi_wready),
      .axi_bresp_i((m_axi_bid == 0) ? m_axi_bresp : AXI_SLVERR),
      .axi_bvalid_i(m_axi_bvalid), .axi_bready_o(m_axi_bready)
  );
endmodule
