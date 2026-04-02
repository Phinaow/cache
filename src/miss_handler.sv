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
    // input  rf_wb_e                           cdc_op_type_i,
    input  logic                             cdc_valid_i,
    output logic                             cdc_ready_o,
    // ----------- //
    // RAM signals
    // ----------- //
    // Addr
    output logic      [MEM_CACHE_ADDR_W-1:0] ram_addr_o,
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

  logic [MEM_CACHE_ADDR_W-1:0] ram_addr_from_refill;
  logic [MEM_CACHE_ADDR_W-1:0] ram_addr_from_writeback;

  // Unused AXI signals
  assign m_axi_awid    = '0;
  assign m_axi_awlock  = 1'b0;
  assign m_axi_awcache = '0;
  assign m_axi_awprot  = '0;
  assign m_axi_awqos   = '0;

  assign m_axi_arid    = '0;
  assign m_axi_arlock  = 1'b0;
  assign m_axi_arcache = '0;
  assign m_axi_arprot  = '0;
  assign m_axi_arqos   = '0;

  // cache_op_t tr_data;

  logic refill_valid;
  logic refill_ready;

  logic writeback_valid;
  logic writeback_ready;

  // assign tr_data.mem_addr = cdc_data_i.addr;
  // assign tr_data.nb_transfer = 8'd127;
  // assign tr_data.cache_addr = '0;

  // logic do_rf_after_wb;

  // always_ff @(posedge clk_i or negedge rst_ni) begin
  //   if(!rst_ni) begin
  //     do_rf_after_wb <= 1'b0;
  //   end else begin
  //     if(writeback_valid && writeback_ready) do_rf_after_wb <= 1;
  //     if(refill_ready && refill_valid) do_rf_after_wb <= 1'b0;
  //   end
  // end

  always_comb begin

    unique case (cdc_data_i.wb_rf)
      REFILL: begin
        ram_addr_o = ram_addr_from_refill;

        refill_valid = cdc_valid_i;
        cdc_ready_o = refill_ready;

        writeback_valid = 1'b0;
      end

      WRITEBACK: begin

        // if(do_rf_after_wb) begin
        //   ram_addr_o = ram_addr_from_refill;

        //   refill_valid = cdc_valid_i;
        //   cdc_ready_o = refill_ready;

        //   writeback_valid = 1'b0;
        // end else begin
        ram_addr_o = ram_addr_from_writeback;

        refill_valid = 1'b0;

        writeback_valid = cdc_valid_i;
        cdc_ready_o = writeback_ready;
        //   cdc_ready_o = 1'b0;
        // end
      end

      default: ;
    endcase

  end


  refill_engine refill_engine_inst (
      .clk_i        (clk_i),
      .rst_ni       (rst_ni),
      .data_i       (cdc_data_i),
      .addr_valid_i (refill_valid),
      .addr_ready_o (refill_ready),
      .ram_addr_o   (ram_addr_from_refill),
      .ram_data_o   (ram_data_o),
      .ram_we_o     (ram_we_o),
      .axi_araddr_o (m_axi_araddr),
      .axi_arlen_o  (m_axi_arlen),
      .axi_arsize_o (m_axi_arsize),
      .axi_arburst_o(m_axi_arburst),
      .axi_arvalid_o(m_axi_arvalid),
      .axi_arready_i(m_axi_arready),
      .axi_rdata_i  (m_axi_rdata),
      .axi_rlast_i  (m_axi_rlast),
      .axi_rvalid_i (m_axi_rvalid),
      .axi_rready_o (m_axi_rready)
  );

  writeback_engine writeback_engine_inst (
      .clk_i        (clk_i),
      .rst_ni       (rst_ni),
      .data_i       (cdc_data_i),
      .addr_valid_i (writeback_valid),
      .addr_ready_o (writeback_ready),
      .ram_addr_o   (ram_addr_from_writeback),
      .ram_data_i   (ram_data_i),
      .axi_awaddr_o (m_axi_awaddr),
      .axi_awlen_o  (m_axi_awlen),
      .axi_awsize_o (m_axi_awsize),
      .axi_awburst_o(m_axi_awburst),
      .axi_awvalid_o(m_axi_awvalid),
      .axi_awready_i(m_axi_awready),
      .axi_wdata_o  (m_axi_wdata),
      .axi_wstrb_o  (m_axi_wstrb),
      .axi_wlast_o  (m_axi_wlast),
      .axi_wvalid_o (m_axi_wvalid),
      .axi_wready_i (m_axi_wready),
      .axi_bresp_i  (m_axi_bresp),
      .axi_bvalid_i (m_axi_bvalid),
      .axi_bready_o (m_axi_bready)
  );

endmodule
