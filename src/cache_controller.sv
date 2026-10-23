module cache_controller
  import cache_pkg::*;
(
    // =======================================Clock and reset=======================================
    input logic clk_i,
    input logic rst_ni,

    // ======================================Write axi signals======================================
    input  logic [CPU_ADDR_W-1:0] axi_awaddr_i,
    input  logic                  axi_awvalid_i,
    output logic                  axi_awready_o,

    input  logic [CPU_DATA_W-1:0] axi_wdata_i,
    input  logic                  axi_wvalid_i,
    output logic                  axi_wready_o,

    input logic [(CPU_DATA_W/8)-1:0] axi_wstrb_i,

    output logic [1:0] axi_bresp_o,
    output logic       axi_bvalid_o,
    input  logic       axi_bready_i,

    // ======================================Read axi signals=======================================
    input  logic [CPU_ADDR_W-1:0] axi_araddr_i,
    input  logic                  axi_arvalid_i,
    output logic                  axi_arready_o,

    output logic [CPU_DATA_W-1:0] axi_rdata_o,
    output logic [           1:0] axi_rresp_o,
    output logic                  axi_rvalid_o,
    input  logic                  axi_rready_i,

    // =========================================CDC signals=========================================
    output logic      cdc_req_valid_o,
    output cdc_data_t cdc_req_data_o,
    input  logic      cdc_req_ready_i,
    input  logic      cdc_resp_valid_i,
    input cache_resp_t cdc_resp_data_i,
    output logic      cdc_resp_ready_o,

    // =========================================RAM signals=========================================
    output logic [CPU_CACHE_ADDR_W-1:0] ram_addr_o,
    output logic ram_en_o,
    output logic [      CPU_DATA_W-1:0] ram_data_o,
    input  logic [      CPU_DATA_W-1:0] ram_data_i,
    output logic [  (CPU_DATA_W/8)-1:0] ram_we_o
);

  logic [  NB_TAG-1:0] access;
  logic                access_valid;
  logic                access_ready;
  logic [  NB_TAG-1:0] lru_way;
  logic                lru_way_valid;


  logic [TAG_SIZE-1:0] awaddr;
  logic                awvalid;
  logic [TAG_SIZE-1:0] araddr;
  logic                arvalid;
  logic                hit;
  logic [1:0] lookup_status;
  logic access_done, write_commit;
  logic [NB_TAG-1:0] commit_way;
  logic [  NB_TAG-1:0] hit_addr;

  hit_detection hit_detection_inst (
      .clk_i           (clk_i),
      .rst_ni          (rst_ni),
      .awvalid_i       (awvalid),
      .awaddr_i        (awaddr),
      .arvalid_i       (arvalid),
      .araddr_i        (araddr),
      .access_done_i   (access_done),
      .write_commit_i  (write_commit),
      .commit_way_i    (commit_way),
      .lookup_status_o (lookup_status),
      .hit_o           (hit),
      .hit_addr_o      (hit_addr),
      .access_data_o   (access),
      .access_valid_o  (access_valid),
      .access_ready_i  (access_ready),
      .lru_way_valid_i (lru_way_valid),
      .lru_way_data_i  (lru_way),
      .cdc_req_valid_o (cdc_req_valid_o),
      .cdc_req_data_o  (cdc_req_data_o),
      .cdc_req_ready_i (cdc_req_ready_i),
      .cdc_resp_valid_i(cdc_resp_valid_i),
      .cdc_resp_data_i (cdc_resp_data_i),
      .cdc_resp_ready_o(cdc_resp_ready_o)
  );

  transaction transaction_inst (
      .clk_i        (clk_i),
      .rst_ni       (rst_ni),
      .axi_awaddr_i (axi_awaddr_i),
      .axi_awvalid_i(axi_awvalid_i),
      .axi_awready_o(axi_awready_o),
      .axi_wdata_i  (axi_wdata_i),
      .axi_wvalid_i (axi_wvalid_i),
      .axi_wready_o (axi_wready_o),
      .axi_wstrb_i  (axi_wstrb_i),
      .axi_bresp_o  (axi_bresp_o),
      .axi_bvalid_o (axi_bvalid_o),
      .axi_bready_i (axi_bready_i),
      .axi_araddr_i (axi_araddr_i),
      .axi_arvalid_i(axi_arvalid_i),
      .axi_arready_o(axi_arready_o),
      .axi_rdata_o  (axi_rdata_o),
      .axi_rresp_o  (axi_rresp_o),
      .axi_rvalid_o (axi_rvalid_o),
      .axi_rready_i (axi_rready_i),
      .awaddr_o     (awaddr),
      .awvalid_o    (awvalid),
      .araddr_o     (araddr),
      .arvalid_o    (arvalid),
      .hit_i        (hit),
      .lookup_status_i(lookup_status),
      .access_done_o(access_done),
      .write_commit_o(write_commit),
      .commit_way_o (commit_way),
      .hit_addr_i   (hit_addr),
      .ram_addr_o   (ram_addr_o),
      .ram_en_o     (ram_en_o),
      .ram_data_o   (ram_data_o),
      .ram_data_i   (ram_data_i),
      .ram_we_o     (ram_we_o)
  );

  plru plru_inst (
      .clk_i          (clk_i),
      .rst_ni         (rst_ni),
      .access_i       (access),
      .access_valid_i (access_valid),
      .access_ready_o (access_ready),
      .lru_way_o      (lru_way),
      .lru_way_valid_o(lru_way_valid)
  );

endmodule
