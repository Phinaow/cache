module transaction
  import cache_pkg::*;
(
    input  logic                  clk_i,
    input  logic                  rst_ni,
    // ----------------- //
    // Write AXI signals
    // ----------------- //
    input  logic [CPU_ADDR_W-1:0] axi_awaddr_i,
    input  logic                  axi_awvalid_i,
    output logic                  axi_awready_o,
    // Data signals
    input  logic [CPU_DATA_W-1:0] axi_wdata_i,
    input  logic                  axi_wvalid_i,
    output logic                  axi_wready_o,
    input  logic [           3:0] axi_wstrb_i,
    // Response signals
    output logic [           1:0] axi_bresp_o,
    output logic                  axi_bvalid_o,
    input  logic                  axi_bready_i,
    // ---------------- //
    // Read AXI signals
    // ---------------- //
    input  logic [CPU_ADDR_W-1:0] axi_araddr_i,
    input  logic                  axi_arvalid_i,
    output logic                  axi_arready_o,
    // Data signals
    output logic [CPU_DATA_W-1:0] axi_rdata_o,
    output logic [           1:0] axi_rresp_o,
    output logic                  axi_rvalid_o,
    input  logic                  axi_rready_i,

    // Hit detection signals
    output logic [TAG_SIZE-1:0] awaddr_o,
    output logic                awvalid_o,

    output logic [TAG_SIZE-1:0] araddr_o,
    output logic                arvalid_o,

    input logic hit_i,
    input logic [NB_TAG-1:0] hit_addr_i,

    // True dual port signals
    output logic [CPU_CACHE_ADDR_W-1:0] ram_addr_o,
    output logic [      CPU_DATA_W-1:0] ram_data_o,
    input  logic [      CPU_DATA_W-1:0] ram_data_i,
    output logic [  (CPU_DATA_W/8)-1:0] ram_we_o
);

  typedef enum {
    StRdIdle,
    StRdAddr,
    StRdData
  } r_state_e;

  typedef enum {
    StWrIdle,
    StWrAddr,
    StWrData,
    StWrResp
  } w_state_e;

  r_state_e r_state_q, r_state_d;
  w_state_e w_state_q, w_state_d;

  logic w_flag;

  logic [CPU_ADDR_W-1:0] raddr_reg;
  logic [CPU_ADDR_W-1:0] waddr_reg;

  logic [WORD_SIZE-1:0] word;

  logic [CPU_ADDR_W-1:0] waddr;
  logic [CPU_ADDR_W-1:0] raddr;

  logic [       OFFSET_SIZE-1:0] offset;
  logic [CPU_ADDR_W-1-TAG_POS:0] overflow;

  assign araddr_o = raddr[TAG_POS-1:WORD_POS];
  assign awaddr_o = waddr[TAG_POS-1:WORD_POS];

  assign word = (w_state_q != StWrIdle) ? waddr[WORD_POS-1:OFFSET_POS] :
                                          raddr[WORD_POS-1:OFFSET_POS];

  assign offset = (w_state_q != StWrIdle) ? waddr[OFFSET_POS-1:0] :
                                            raddr[OFFSET_POS-1:0];

  assign overflow = (w_state_q != StWrIdle) ? waddr[CPU_ADDR_W-1:TAG_POS] :
                                              raddr[CPU_ADDR_W-1:TAG_POS];

  assign ram_addr_o = {hit_addr_i, word};

  assign axi_rdata_o = ram_data_i;
  assign ram_data_o  = axi_wdata_i;
  assign ram_we_o    = (axi_wready_o && axi_wvalid_i) ? axi_wstrb_i : '0;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if(!rst_ni) begin
      r_state_q <= StRdIdle;
      w_state_q <= StWrIdle;

      w_flag <= 1'b0;

      raddr_reg <= '0;
      waddr_reg <= '0;
    end else begin
      r_state_q <= r_state_d;
      w_state_q <= w_state_d;

      if(axi_awvalid_i && axi_awready_o) begin
        w_flag <= 1'b0;
      end else if(
        axi_arvalid_i &&
        axi_awvalid_i &&
        r_state_q == StRdIdle &&
        w_state_q == StWrIdle
      ) begin
        w_flag <= 1'b1;
      end

      if(axi_arvalid_i && axi_arready_o) raddr_reg <= axi_araddr_i;
      if(axi_awvalid_i && axi_awready_o) waddr_reg <= axi_awaddr_i;
    end
  end

  always_comb begin
    r_state_d = r_state_q;

    axi_arready_o = 1'b0;
    axi_rvalid_o = 1'b0;

    arvalid_o = 1'b0;
    raddr = raddr_reg;

    axi_rresp_o = (overflow != '0 || offset != '0) ? 2'b10 : 2'b00;

    unique case (r_state_q)
      StRdIdle: begin
        raddr = axi_araddr_i;

        if(axi_arvalid_i && w_state_q == StWrIdle && !w_flag) begin
          arvalid_o = 1'b1;
          axi_arready_o = 1'b1;
          r_state_d = StRdAddr;
        end
      end

      StRdAddr: begin

        arvalid_o = 1'b1;

        if(hit_i && axi_rready_i) begin
          axi_rvalid_o = 1'b1;
          r_state_d = StRdIdle;
        end else begin
          r_state_d = StRdData;
        end

        // if(hit_i) r_state_d = StRdData;
      end

      StRdData: begin
        arvalid_o = 1'b1;
        // axi_rvalid_o = 1'b1;
        // if(axi_rready_i && axi_rvalid_o) r_state_d = StRdIdle;

        if(hit_i && axi_rready_i) begin
          axi_rvalid_o = 1'b1;
          r_state_d = StRdIdle;
        end
      end

      default: ;
    endcase
  end

  always_comb begin
    w_state_d = w_state_q;

    axi_awready_o = 1'b0;
    axi_wready_o = 1'b0;
    axi_bvalid_o = 1'b0;

    awvalid_o = 1'b0;
    waddr = waddr_reg;

    axi_bresp_o = (overflow != '0 || offset != '0) ? 2'b10 : 2'b00;

    unique case (w_state_q)
      StWrIdle: begin

        if(axi_awvalid_i && r_state_q == StRdIdle && (!axi_arvalid_i || w_flag)) begin
          waddr = axi_awaddr_i;
          axi_awready_o = 1'b1;
          w_state_d = StWrAddr;
        end
      end

      StWrAddr: begin
        awvalid_o = 1'b1;

        if(hit_i && axi_wvalid_i) begin
          axi_wready_o = 1'b1;
          axi_bvalid_o = 1'b1;

          if(axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
          else w_state_d = StWrResp;

        end else begin
          w_state_d = StWrData;
        end

        // if(hit_i) w_state_d = StWrData;
      end

      StWrData: begin
        awvalid_o = 1'b1;

        if(hit_i && axi_wvalid_i) begin
          axi_wready_o = 1'b1;
          axi_bvalid_o = 1'b1;

          if(axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
          else w_state_d = StWrResp;
        end

        // if(axi_wvalid_i) begin
        //   axi_wready_o = 1'b1;
        //   axi_bvalid_o = 1'b1;
        //   if(axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
        //   else w_state_d = StWrResp;
        // end
      end

      StWrResp: begin
        axi_bvalid_o = 1'b1;

        if(axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
      end

      default: ;
    endcase
  end

endmodule
