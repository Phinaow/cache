module miss_handler
  import cache_pkg::*;
(
    // ----------------------- //
    // Clock and reset signals
    // ----------------------- //
    input  logic                        clk_i,
    input  logic                        rst_ni,
    // Control signals
    input  logic                        refill_i,
    input  logic                        writeback_i,
    output logic                        done_o,
    input  logic [      MEM_ADDR_W-1:0] mig_addr_i,
    // ----------- //
    // RAM signals
    // ----------- //
    // Addr
    output logic [MEM_CACHE_ADDR_W-1:0] ram_addr_o,
    // Read data from ram
    input  logic [      MEM_DATA_W-1:0] ram_data_i,
    // Write data in ram
    output logic [      MEM_DATA_W-1:0] ram_data_o,
    output logic [                15:0] ram_we_o,
    // ----------------- //
    // Write AXI signals
    // ----------------- //
    // Config signals
    output logic [                 1:0] m_axi_awid,
    output logic [      MEM_ADDR_W-1:0] m_axi_awaddr,
    output logic [                 7:0] m_axi_awlen,
    output logic [                 2:0] m_axi_awsize,
    output logic [                 1:0] m_axi_awburst,
    output logic [                 0:0] m_axi_awlock,
    output logic [                 3:0] m_axi_awcache,
    output logic [                 2:0] m_axi_awprot,
    output logic [                 3:0] m_axi_awqos,
    output logic                        m_axi_awvalid,
    input  logic                        m_axi_awready,
    // Data signals
    output logic [      MEM_DATA_W-1:0] m_axi_wdata,
    output logic [    MEM_DATA_W/8-1:0] m_axi_wstrb,
    output logic                        m_axi_wlast,
    output logic                        m_axi_wvalid,
    input  logic                        m_axi_wready,
    // Response signals
    input  logic [                 1:0] m_axi_bid,
    input  logic [                 1:0] m_axi_bresp,
    input  logic                        m_axi_bvalid,
    output logic                        m_axi_bready,
    // ---------------- //
    // Read AXI signals
    // ---------------- //
    // Config signals
    output logic [                 1:0] m_axi_arid,
    output logic [      MEM_ADDR_W-1:0] m_axi_araddr,
    output logic [                 7:0] m_axi_arlen,
    output logic [                 2:0] m_axi_arsize,
    output logic [                 1:0] m_axi_arburst,
    output logic [                 0:0] m_axi_arlock,
    output logic [                 3:0] m_axi_arcache,
    output logic [                 2:0] m_axi_arprot,
    output logic [                 3:0] m_axi_arqos,
    output logic                        m_axi_arvalid,
    input  logic                        m_axi_arready,
    // Data signals
    input  logic [                 1:0] m_axi_rid,
    input  logic [      MEM_DATA_W-1:0] m_axi_rdata,
    input  logic [                 1:0] m_axi_rresp,
    input  logic                        m_axi_rlast,
    input  logic                        m_axi_rvalid,
    output logic                        m_axi_rready
);

  logic refill_cmd;
  logic writeback_cmd;

  logic refill_done;
  logic writeback_done;

  logic start_refill;
  logic start_writeback;

  logic refill_busy;
  logic writeback_busy;

  logic [MEM_ADDR_W-1:0] refill_addr;
  logic [MEM_ADDR_W-1:0] writeback_addr;

  logic [MEM_CACHE_ADDR_W-1:0] ram_addr_from_refill;
  logic [MEM_CACHE_ADDR_W-1:0] ram_addr_from_writeback;

  typedef enum logic [1:0] {
    StIdle,
    StWriteback,
    StRefill
  } state_e;

  state_e state_q, state_d;

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

  always_ff @(posedge clk_i or negedge rst_ni) begin

    if (!rst_ni) begin
      refill_cmd    <= 1'b0;
      writeback_cmd <= 1'b0;
    end else begin

      if (refill_i) begin
        refill_cmd  <= 1'b1;
        refill_addr <= mig_addr_i;
      end else if (refill_done) begin
        refill_cmd <= 1'b0;
      end

      if (writeback_i) begin
        writeback_cmd  <= 1'b1;
        writeback_addr <= mig_addr_i;
      end else if (writeback_done) begin
        writeback_cmd <= 1'b0;
      end

    end

  end

  assign done_o = writeback_done || refill_done;

  always_comb begin
    if (refill_cmd) begin
      ram_addr_o = ram_addr_from_refill;
    end else if (writeback_cmd) begin
      ram_addr_o = ram_addr_from_writeback;
    end else begin
      ram_addr_o = '0;
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q <= StIdle;
    end else begin
      state_q <= state_d;
    end
  end

  always_comb begin
    start_refill    = 1'b0;
    start_writeback = 1'b0;
    state_d         = state_q;

    unique case (state_q)
      StIdle: begin
        if (!refill_busy && !writeback_busy) begin
          if (writeback_cmd) begin
            start_writeback = 1'b1;
            state_d         = StWriteback;
          end else if (refill_cmd) begin
            start_refill = 1'b1;
            state_d      = StRefill;
          end
        end
      end

      StWriteback: begin
        if (writeback_done) begin
          state_d = StIdle;
        end
      end

      StRefill: begin
        if (refill_done) begin
          state_d = StIdle;
        end
      end

      default:;
    endcase
  end


  refill_engine refill_engine_inst (
      .clk_i         (clk_i),
      .rst_ni        (rst_ni),
      .start_refill_i(start_refill),
      .target_addr_i (refill_addr),
      .busy_o        (refill_busy),
      .done_o        (refill_done),
      .ram_addr_o    (ram_addr_from_refill),
      .ram_data_o    (ram_data_o),
      .ram_we_o      (ram_we_o),
      .axi_araddr_o  (m_axi_araddr),
      .axi_arlen_o   (m_axi_arlen),
      .axi_arsize_o  (m_axi_arsize),
      .axi_arburst_o (m_axi_arburst),
      .axi_arvalid_o (m_axi_arvalid),
      .axi_arready_i (m_axi_arready),
      .axi_rdata_i   (m_axi_rdata),
      .axi_rlast_i   (m_axi_rlast),
      .axi_rvalid_i  (m_axi_rvalid),
      .axi_rready_o  (m_axi_rready)
  );

  writeback_engine writeback_engine_inst (
      .clk_i        (clk_i),
      .rst_ni       (rst_ni),
      .start_wb_i   (start_writeback),
      .target_addr_i(writeback_addr),
      .busy_o       (writeback_busy),
      .done_o       (writeback_done),
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
