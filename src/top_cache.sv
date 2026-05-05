module top_cache
  import cache_pkg::*;
(
    // input  logic                    sys_clk_i   ,
    input  logic                    rst_ni,
    input  logic                    clk_mig_i,
    input  logic                    clk_ref_i,
    input  logic                    clk_cpu_i,
    // --- //
    // AXI
    // --- //
    input  logic [  CPU_ADDR_W-1:0] axi_awaddr_i,
    input  logic                    axi_awvalid_i,
    output logic                    axi_awready_o,
    input  logic [  CPU_DATA_W-1:0] axi_wdata_i,
    input  logic                    axi_wvalid_i,
    output logic                    axi_wready_o,
    input  logic [CPU_DATA_W/8-1:0] axi_wstrb_i,
    output logic [             1:0] axi_bresp_o,
    output logic                    axi_bvalid_o,
    input  logic                    axi_bready_i,
    input  logic [  CPU_ADDR_W-1:0] axi_araddr_i,
    input  logic                    axi_arvalid_i,
    output logic                    axi_arready_o,
    output logic [  CPU_DATA_W-1:0] axi_rdata_o,
    output logic [             1:0] axi_rresp_o,
    output logic                    axi_rvalid_o,
    input  logic                    axi_rready_i,
    // ---- //
    // DRAM
    // ---- //
    inout  logic [            15:0] ddr3_dq,
    inout  logic [             1:0] ddr3_dqs_n,
    inout  logic [             1:0] ddr3_dqs_p,
    output logic [            14:0] ddr3_addr,
    output logic [             2:0] ddr3_ba,
    output logic                    ddr3_ras_n,
    output logic                    ddr3_cas_n,
    output logic                    ddr3_we_n,
    output logic                    ddr3_reset_n,
    output logic [             0:0] ddr3_ck_p,
    output logic [             0:0] ddr3_ck_n,
    output logic [             0:0] ddr3_cke,
    output logic [             1:0] ddr3_dm,
    output logic [             0:0] ddr3_odt
);



  logic [             1:0] dram_axi_awid;
  logic [  MEM_ADDR_W-1:0] dram_axi_awaddr;
  logic [             7:0] dram_axi_awlen;
  logic [             2:0] dram_axi_awsize;
  logic [             1:0] dram_axi_awburst;
  logic [             0:0] dram_axi_awlock;
  logic [             3:0] dram_axi_awcache;
  logic [             2:0] dram_axi_awprot;
  logic [             3:0] dram_axi_awqos;
  logic                    dram_axi_awvalid;
  logic                    dram_axi_awready;
  logic [  MEM_DATA_W-1:0] dram_axi_wdata;
  logic [MEM_DATA_W/8-1:0] dram_axi_wstrb;
  logic                    dram_axi_wlast;
  logic                    dram_axi_wvalid;
  logic                    dram_axi_wready;
  logic [             1:0] dram_axi_bid;
  logic [             1:0] dram_axi_bresp;
  logic                    dram_axi_bvalid;
  logic                    dram_axi_bready;
  logic [             1:0] dram_axi_arid;
  logic [  MEM_ADDR_W-1:0] dram_axi_araddr;
  logic [             7:0] dram_axi_arlen;
  logic [             2:0] dram_axi_arsize;
  logic [             1:0] dram_axi_arburst;
  logic [             0:0] dram_axi_arlock;
  logic [             3:0] dram_axi_arcache;
  logic [             2:0] dram_axi_arprot;
  logic [             3:0] dram_axi_arqos;
  logic                    dram_axi_arvalid;
  logic                    dram_axi_arready;
  logic [             1:0] dram_axi_rid;
  logic [  MEM_DATA_W-1:0] dram_axi_rdata;
  logic [             1:0] dram_axi_rresp;
  logic                    dram_axi_rlast;
  logic                    dram_axi_rvalid;
  logic                    dram_axi_rready;

  logic                    ui_clk;
  logic                    ui_clk_sync_rst;
  logic                    aresetn;

  assign aresetn = ~ui_clk_sync_rst;

  logic                             controller_valid_cdc;
  logic                             controller_ready_cdc;
  cdc_data_t                        controller_data_cdc;

  logic      [CPU_CACHE_ADDR_W-1:0] controller_to_cache_addr;
  logic      [      CPU_DATA_W-1:0] controller_to_cache_data;
  logic      [      CPU_DATA_W-1:0] cache_to_controller_data;
  logic      [  (CPU_DATA_W/8)-1:0] controller_to_cache_we;

  logic                             controller_resp_valid;
  logic                             controller_resp_ready;
  rf_wb_e                           controller_resp_data;

  logic                             miss_handler_valid_cdc;
  logic                             miss_handler_ready_cdc;
  cdc_data_t                        miss_handler_data_cdc;

  logic                             miss_resp_ready;
  logic                             miss_resp_valid;
  rf_wb_e                           miss_resp_data;

  logic      [MEM_CACHE_ADDR_W-1:0] miss_handler_to_cache_addr;
  logic      [      MEM_DATA_W-1:0] cache_to_miss_handler_data;
  logic      [      MEM_DATA_W-1:0] miss_handler_to_cache_data;
  logic      [  (MEM_DATA_W/8)-1:0] miss_handler_to_cache_we;



  cache_controller cache_controller_inst (
      .clk_i           (clk_cpu_i),
      .rst_ni          (rst_ni),
      .axi_awaddr_i    (axi_awaddr_i),
      .axi_awvalid_i   (axi_awvalid_i),
      .axi_awready_o   (axi_awready_o),
      .axi_wdata_i     (axi_wdata_i),
      .axi_wvalid_i    (axi_wvalid_i),
      .axi_wready_o    (axi_wready_o),
      .axi_wstrb_i     (axi_wstrb_i),
      .axi_bresp_o     (axi_bresp_o),
      .axi_bvalid_o    (axi_bvalid_o),
      .axi_bready_i    (axi_bready_i),
      .axi_araddr_i    (axi_araddr_i),
      .axi_arvalid_i   (axi_arvalid_i),
      .axi_arready_o   (axi_arready_o),
      .axi_rdata_o     (axi_rdata_o),
      .axi_rresp_o     (axi_rresp_o),
      .axi_rvalid_o    (axi_rvalid_o),
      .axi_rready_i    (axi_rready_i),
      .cdc_req_valid_o (controller_valid_cdc),
      .cdc_req_data_o  (controller_data_cdc),
      .cdc_req_ready_i (controller_ready_cdc),
      .cdc_resp_valid_i(controller_resp_valid),
      .cdc_resp_ready_o(controller_resp_ready),
      .ram_addr_o      (controller_to_cache_addr),
      .ram_data_o      (controller_to_cache_data),
      .ram_data_i      (cache_to_controller_data),
      .ram_we_o        (controller_to_cache_we)
  );


  cdc_handshake #(
      .T(cdc_data_t)
  ) controller_req (
      .clk_src_i  (clk_cpu_i),
      .rst_src_ni (rst_ni),
      .src_data_i (controller_data_cdc),
      .src_valid_i(controller_valid_cdc),
      .src_ready_o(controller_ready_cdc),
      .clk_dst_i  (ui_clk),
      .rst_dst_ni (rst_ni),
      .dst_data_o (miss_handler_data_cdc),
      .dst_valid_o(miss_handler_valid_cdc),
      .dst_ready_i(miss_handler_ready_cdc)
  );

  cdc_handshake #(
      .T(rf_wb_e)
  ) miss_handler_resp (
      .clk_src_i  (ui_clk),
      .rst_src_ni (rst_ni),
      .src_data_i (miss_resp_data),
      .src_valid_i(miss_resp_valid),
      .src_ready_o(miss_resp_ready),
      .clk_dst_i  (clk_cpu_i),
      .rst_dst_ni (rst_ni),
      .dst_data_o (controller_resp_data),
      .dst_valid_o(controller_resp_valid),
      .dst_ready_i(controller_resp_ready)
  );


  miss_handler miss_handler_inst (
      .clk_i        (ui_clk),
      .rst_ni       (rst_ni),
      .cdc_data_i   (miss_handler_data_cdc),
      .cdc_valid_i  (miss_handler_valid_cdc),
      .cdc_ready_o  (miss_handler_ready_cdc),
      .resp_data_o  (miss_resp_data),
      .resp_valid_o (miss_resp_valid),
      .resp_ready_i (miss_resp_ready),
      .ram_addr_o   (miss_handler_to_cache_addr),
      .ram_data_i   (cache_to_miss_handler_data),
      .ram_data_o   (miss_handler_to_cache_data),
      .ram_we_o     (miss_handler_to_cache_we),
      .m_axi_awid   (dram_axi_awid),
      .m_axi_awaddr (dram_axi_awaddr),
      .m_axi_awlen  (dram_axi_awlen),
      .m_axi_awsize (dram_axi_awsize),
      .m_axi_awburst(dram_axi_awburst),
      .m_axi_awlock (dram_axi_awlock),
      .m_axi_awcache(dram_axi_awcache),
      .m_axi_awprot (dram_axi_awprot),
      .m_axi_awqos  (dram_axi_awqos),
      .m_axi_awvalid(dram_axi_awvalid),
      .m_axi_awready(dram_axi_awready),
      .m_axi_wdata  (dram_axi_wdata),
      .m_axi_wstrb  (dram_axi_wstrb),
      .m_axi_wlast  (dram_axi_wlast),
      .m_axi_wvalid (dram_axi_wvalid),
      .m_axi_wready (dram_axi_wready),
      .m_axi_bid    (dram_axi_bid),
      .m_axi_bresp  (dram_axi_bresp),
      .m_axi_bvalid (dram_axi_bvalid),
      .m_axi_bready (dram_axi_bready),
      .m_axi_arid   (dram_axi_arid),
      .m_axi_araddr (dram_axi_araddr),
      .m_axi_arlen  (dram_axi_arlen),
      .m_axi_arsize (dram_axi_arsize),
      .m_axi_arburst(dram_axi_arburst),
      .m_axi_arlock (dram_axi_arlock),
      .m_axi_arcache(dram_axi_arcache),
      .m_axi_arprot (dram_axi_arprot),
      .m_axi_arqos  (dram_axi_arqos),
      .m_axi_arvalid(dram_axi_arvalid),
      .m_axi_arready(dram_axi_arready),
      .m_axi_rid    (dram_axi_rid),
      .m_axi_rdata  (dram_axi_rdata),
      .m_axi_rresp  (dram_axi_rresp),
      .m_axi_rlast  (dram_axi_rlast),
      .m_axi_rvalid (dram_axi_rvalid),
      .m_axi_rready (dram_axi_rready)
  );


  true_dual_port_ram true_dual_port_ram_inst (
      .clkb (clk_cpu_i),
      .clka (ui_clk),
      .web  (controller_to_cache_we),
      .wea  (miss_handler_to_cache_we),
      .enb  (1'b1),
      .ena  (1'b1),
      .addrb(controller_to_cache_addr),
      .addra(miss_handler_to_cache_addr),
      .dinb (controller_to_cache_data),
      .dina (miss_handler_to_cache_data),
      .doutb(cache_to_controller_data),
      .douta(cache_to_miss_handler_data)
  );

  logic init_calib_complete;
  logic mmcm_locked;

  logic ui_addn_clk_0;
  logic ui_addn_clk_1;
  logic ui_addn_clk_2;
  logic ui_addn_clk_3;
  logic ui_addn_clk_4;

  adam_mig mig_inst (
      // DDR3 ports memory
      .ddr3_addr   (ddr3_addr),
      .ddr3_ba     (ddr3_ba),
      .ddr3_cas_n  (ddr3_cas_n),
      .ddr3_ck_n   (ddr3_ck_n),
      .ddr3_ck_p   (ddr3_ck_p),
      .ddr3_cke    (ddr3_cke),
      .ddr3_ras_n  (ddr3_ras_n),
      .ddr3_we_n   (ddr3_we_n),
      .ddr3_dq     (ddr3_dq),
      .ddr3_dqs_n  (ddr3_dqs_n),
      .ddr3_dqs_p  (ddr3_dqs_p),
      .ddr3_reset_n(ddr3_reset_n),
      .ddr3_dm     (ddr3_dm),
      .ddr3_odt    (ddr3_odt),

      // User clock interface
      .ui_clk             (ui_clk),
      .ui_clk_sync_rst    (ui_clk_sync_rst),
      .mmcm_locked        (mmcm_locked),
      .aresetn            (aresetn),
      .app_sr_active      (),
      .app_ref_ack        (),
      .app_zq_ack         (),
      .app_sr_req         (1'b0),
      .app_ref_req        (1'b0),
      .app_zq_req         (1'b0),
      .init_calib_complete(init_calib_complete),

      // AXI4 Write interface
      .s_axi_awid   (dram_axi_awid),
      .s_axi_awaddr (dram_axi_awaddr[28:0]),
      .s_axi_awlen  (dram_axi_awlen),
      .s_axi_awsize (dram_axi_awsize),
      .s_axi_awburst(dram_axi_awburst),
      .s_axi_awlock (dram_axi_awlock),
      .s_axi_awcache(dram_axi_awcache),
      .s_axi_awprot (dram_axi_awprot),
      .s_axi_awqos  (dram_axi_awqos),
      .s_axi_awvalid(dram_axi_awvalid),
      .s_axi_awready(dram_axi_awready),

      .s_axi_wdata (dram_axi_wdata),
      .s_axi_wstrb (dram_axi_wstrb),
      .s_axi_wlast (dram_axi_wlast),
      .s_axi_wvalid(dram_axi_wvalid),
      .s_axi_wready(dram_axi_wready),

      .s_axi_bid   (dram_axi_bid),
      .s_axi_bresp (dram_axi_bresp),
      .s_axi_bvalid(dram_axi_bvalid),
      .s_axi_bready(dram_axi_bready),

      // AXI read interfacedram_a
      .s_axi_arid   (dram_axi_arid),
      .s_axi_araddr (dram_axi_araddr[28:0]),
      .s_axi_arlen  (dram_axi_arlen),
      .s_axi_arsize (dram_axi_arsize),
      .s_axi_arburst(dram_axi_arburst),
      .s_axi_arlock (dram_axi_arlock),
      .s_axi_arcache(dram_axi_arcache),
      .s_axi_arprot (dram_axi_arprot),
      .s_axi_arqos  (dram_axi_arqos),
      .s_axi_arvalid(dram_axi_arvalid),
      .s_axi_arready(dram_axi_arready),

      .s_axi_rid   (dram_axi_rid),
      .s_axi_rdata (dram_axi_rdata),
      .s_axi_rresp (dram_axi_rresp),
      .s_axi_rlast (dram_axi_rlast),
      .s_axi_rvalid(dram_axi_rvalid),
      .s_axi_rready(dram_axi_rready),

      .ui_addn_clk_0(ui_addn_clk_0),
      .ui_addn_clk_1(ui_addn_clk_1),
      .ui_addn_clk_2(ui_addn_clk_2),
      .ui_addn_clk_3(ui_addn_clk_3),
      .ui_addn_clk_4(ui_addn_clk_4),

      // Clocks system
      .sys_clk_i  (clk_mig_i),
      .clk_ref_i  (clk_ref_i),
      .device_temp(),
      .sys_rst    (rst_ni)
  );


endmodule
