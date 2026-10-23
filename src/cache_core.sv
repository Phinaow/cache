// Simulation-friendly cache core: CPU AXI-Lite to memory AXI, with two clocks.
module cache_core import cache_pkg::*;
#(parameter bit USE_VENDOR_RAM = 1'b0)
(
    input logic rst_ni,
    input logic clk_cpu_i,
    input logic clk_mem_i,
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
    output logic      [      MEM_DATA_W-1:0] m_axi_wdata,
    output logic      [    MEM_DATA_W/8-1:0] m_axi_wstrb,
    output logic                             m_axi_wlast,
    output logic                             m_axi_wvalid,
    input  logic                             m_axi_wready,
    input  logic      [                 1:0] m_axi_bid,
    input  logic      [                 1:0] m_axi_bresp,
    input  logic                             m_axi_bvalid,
    output logic                             m_axi_bready,
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
    input  logic      [                 1:0] m_axi_rid,
    input  logic      [      MEM_DATA_W-1:0] m_axi_rdata,
    input  logic      [                 1:0] m_axi_rresp,
    input  logic                             m_axi_rlast,
    input  logic                             m_axi_rvalid,
    output logic                             m_axi_rready
);
  initial begin
    assert (NB_LINE > 0 && (NB_LINE & (NB_LINE - 1)) == 0 &&
            CPU_DATA_W >= 8 && (CPU_DATA_W & (CPU_DATA_W - 1)) == 0 &&
            MEM_DATA_W >= CPU_DATA_W && MEM_DATA_W % CPU_DATA_W == 0 &&
            (MEM_DATA_W & (MEM_DATA_W - 1)) == 0 &&
            CPU_CACHE_SIZE % NB_LINE == 0 && LINE_SIZE >= MEM_DATA_W / 8 &&
            (LINE_SIZE & (LINE_SIZE - 1)) == 0 && LINE_SIZE <= 4096 &&
            LINE_SIZE / (MEM_DATA_W / 8) <= 256 &&
            (MEM_SIZE & (MEM_SIZE - 1)) == 0 && TAG_POS < CPU_ADDR_W)
      else $fatal(1, "Unsupported cache geometry or AXI burst length");
  end
  logic rst_cpu_n, rst_mem_n;
  logic cpu_ram_enable, memory_ram_enable;
  reset_sync cpu_reset (.clk_i(clk_cpu_i), .rst_ni(rst_ni), .rst_no(rst_cpu_n));
  reset_sync memory_reset (.clk_i(clk_mem_i), .rst_ni(rst_ni), .rst_no(rst_mem_n));
  logic                             controller_valid_cdc;
  logic                             controller_ready_cdc;
  cdc_data_t                        controller_data_cdc;

  logic      [CPU_CACHE_ADDR_W-1:0] controller_to_cache_addr;
  logic      [      CPU_DATA_W-1:0] controller_to_cache_data;
  logic      [      CPU_DATA_W-1:0] cache_to_controller_data;
  logic      [  (CPU_DATA_W/8)-1:0] controller_to_cache_we;

  logic                             controller_resp_valid;
  logic                             controller_resp_ready;
  cache_resp_t                      controller_resp_data;

  logic                             miss_handler_valid_cdc;
  logic                             miss_handler_ready_cdc;
  cdc_data_t                        miss_handler_data_cdc;

  logic                             miss_resp_ready;
  logic                             miss_resp_valid;
  cache_resp_t                      miss_resp_data;

  logic      [MEM_CACHE_ADDR_W-1:0] miss_handler_to_cache_addr;
  logic      [      MEM_DATA_W-1:0] cache_to_miss_handler_data;
  logic      [      MEM_DATA_W-1:0] miss_handler_to_cache_data;
  logic      [  (MEM_DATA_W/8)-1:0] miss_handler_to_cache_we;



  cache_controller cache_controller_inst (
      .clk_i           (clk_cpu_i),
      .rst_ni          (rst_cpu_n),
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
      .cdc_resp_data_i (controller_resp_data),
      .cdc_resp_ready_o(controller_resp_ready),
      .ram_addr_o      (controller_to_cache_addr),
      .ram_en_o        (cpu_ram_enable),
      .ram_data_o      (controller_to_cache_data),
      .ram_data_i      (cache_to_controller_data),
      .ram_we_o        (controller_to_cache_we)
  );


  cdc_handshake #(
      .T(cdc_data_t)
  ) controller_req (
      .clk_src_i  (clk_cpu_i),
      .rst_src_ni (rst_cpu_n),
      .src_data_i (controller_data_cdc),
      .src_valid_i(controller_valid_cdc),
      .src_ready_o(controller_ready_cdc),
      .clk_dst_i  (clk_mem_i),
      .rst_dst_ni (rst_mem_n),
      .dst_data_o (miss_handler_data_cdc),
      .dst_valid_o(miss_handler_valid_cdc),
      .dst_ready_i(miss_handler_ready_cdc)
  );

  cdc_handshake #(
      .T(cache_resp_t)
  ) miss_handler_resp (
      .clk_src_i  (clk_mem_i),
      .rst_src_ni (rst_mem_n),
      .src_data_i (miss_resp_data),
      .src_valid_i(miss_resp_valid),
      .src_ready_o(miss_resp_ready),
      .clk_dst_i  (clk_cpu_i),
      .rst_dst_ni (rst_cpu_n),
      .dst_data_o (controller_resp_data),
      .dst_valid_o(controller_resp_valid),
      .dst_ready_i(controller_resp_ready)
  );


  miss_handler miss_handler_inst (
      .clk_i        (clk_mem_i),
      .rst_ni       (rst_mem_n),
      .cdc_data_i   (miss_handler_data_cdc),
      .cdc_valid_i  (miss_handler_valid_cdc),
      .cdc_ready_o  (miss_handler_ready_cdc),
      .resp_data_o  (miss_resp_data),
      .resp_valid_o (miss_resp_valid),
      .resp_ready_i (miss_resp_ready),
      .ram_addr_o   (miss_handler_to_cache_addr),
      .ram_en_o     (memory_ram_enable),
      .ram_data_i   (cache_to_miss_handler_data),
      .ram_data_o   (miss_handler_to_cache_data),
      .ram_we_o     (miss_handler_to_cache_we),
      .m_axi_awid   (m_axi_awid),
      .m_axi_awaddr (m_axi_awaddr),
      .m_axi_awlen  (m_axi_awlen),
      .m_axi_awsize (m_axi_awsize),
      .m_axi_awburst(m_axi_awburst),
      .m_axi_awlock (m_axi_awlock),
      .m_axi_awcache(m_axi_awcache),
      .m_axi_awprot (m_axi_awprot),
      .m_axi_awqos  (m_axi_awqos),
      .m_axi_awvalid(m_axi_awvalid),
      .m_axi_awready(m_axi_awready),
      .m_axi_wdata  (m_axi_wdata),
      .m_axi_wstrb  (m_axi_wstrb),
      .m_axi_wlast  (m_axi_wlast),
      .m_axi_wvalid (m_axi_wvalid),
      .m_axi_wready (m_axi_wready),
      .m_axi_bid    (m_axi_bid),
      .m_axi_bresp  (m_axi_bresp),
      .m_axi_bvalid (m_axi_bvalid),
      .m_axi_bready (m_axi_bready),
      .m_axi_arid   (m_axi_arid),
      .m_axi_araddr (m_axi_araddr),
      .m_axi_arlen  (m_axi_arlen),
      .m_axi_arsize (m_axi_arsize),
      .m_axi_arburst(m_axi_arburst),
      .m_axi_arlock (m_axi_arlock),
      .m_axi_arcache(m_axi_arcache),
      .m_axi_arprot (m_axi_arprot),
      .m_axi_arqos  (m_axi_arqos),
      .m_axi_arvalid(m_axi_arvalid),
      .m_axi_arready(m_axi_arready),
      .m_axi_rid    (m_axi_rid),
      .m_axi_rdata  (m_axi_rdata),
      .m_axi_rresp  (m_axi_rresp),
      .m_axi_rlast  (m_axi_rlast),
      .m_axi_rvalid (m_axi_rvalid),
      .m_axi_rready (m_axi_rready)
  );


  true_dual_port_ram #(.USE_VENDOR_RAM(USE_VENDOR_RAM)) true_dual_port_ram_inst (
      .clkb (clk_cpu_i),
      .clka (clk_mem_i),
      .web  (controller_to_cache_we),
      .wea  (miss_handler_to_cache_we),
      .enb  (cpu_ram_enable),
      .ena  (memory_ram_enable),
      .addrb(controller_to_cache_addr),
      .addra(miss_handler_to_cache_addr),
      .dinb (controller_to_cache_data),
      .dina (miss_handler_to_cache_data),
      .doutb(cache_to_controller_data),
      .douta(cache_to_miss_handler_data)
  );

endmodule
