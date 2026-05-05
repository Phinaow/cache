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
    output logic      cdc_resp_ready_o,

    // =========================================RAM signals=========================================
    output logic [CPU_CACHE_ADDR_W-1:0] ram_addr_o,
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
  logic [  NB_TAG-1:0] hit_addr;

  hit_detection hit_detection_inst (
      .clk_i           (clk_i),
      .rst_ni          (rst_ni),
      .awvalid_i       (awvalid),
      .awaddr_i        (awaddr),
      .arvalid_i       (arvalid),
      .araddr_i        (araddr),
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
      .hit_addr_i   (hit_addr),
      .ram_addr_o   (ram_addr_o),
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
































// module cache_controller
//   import cache_pkg::*;
// (
//     input  logic                  clk_i,
//     input  logic                  rst_ni,
//     // ----------------- //
//     // Write AXI signals
//     // ----------------- //
//     // Config signals
//     input  logic [CPU_ADDR_W-1:0] axi_awaddr_i,
//     input  logic                  axi_awvalid_i,
//     output logic                  axi_awready_o,
//     // Data signals
//     input  logic [CPU_DATA_W-1:0] axi_wdata_i,
//     input  logic                  axi_wvalid_i,
//     output logic                  axi_wready_o,
//     input  logic [           3:0] axi_wstrb_i,
//     // Response signals
//     output logic [           1:0] axi_bresp_o,
//     output logic                  axi_bvalid_o,
//     input  logic                  axi_bready_i,
//     // ---------------- //
//     // Read AXI signals
//     // ---------------- //
//     // Config signals
//     input  logic [CPU_ADDR_W-1:0] axi_araddr_i,
//     input  logic                  axi_arvalid_i,
//     output logic                  axi_arready_o,
//     // Data signals
//     output logic [CPU_DATA_W-1:0] axi_rdata_o,
//     output logic [           1:0] axi_rresp_o,
//     output logic                  axi_rvalid_o,
//     input  logic                  axi_rready_i,

//     output logic [CPU_CACHE_ADDR_W-1:0] ram_addr_o,
//     output logic [      CPU_DATA_W-1:0] ram_data_o,
//     input  logic [      CPU_DATA_W-1:0] ram_data_i,
//     output logic [  (CPU_DATA_W/8)-1:0] ram_we_o,

//     output cdc_data_t cdc_data_o,
//     output logic      cdc_valid_o,
//     input  logic      cdc_ready_i,

//     input  rf_wb_e resp_data_i,
//     input  logic   resp_valid_i,
//     output logic   resp_ready_o
// );
//   localparam int unsigned NbLvl = $clog2(NB_LINE);
//   localparam int MemOffset = $clog2(MEM_CACHE_SIZE / NB_LINE);


//   logic [          TAG_SIZE-1:0] tags [NB_LINE];
//   logic [           NB_LINE-1:0] tag_valid;
//   logic [           NB_LINE-1:0] dirty;


//   logic [        CPU_ADDR_W-1:0] addr;
//   logic [         WORD_SIZE-1:0] word;
//   logic [       OFFSET_SIZE-1:0] offset;  // kept for future misalignment detection
//   logic [CPU_ADDR_W-1-TAG_POS:0] overflow;  // kept for future SLVERR detection

//   assign word     = addr[WORD_POS-1:OFFSET_POS];
//   assign offset   = addr[OFFSET_POS-1:0];
//   assign overflow = addr[CPU_ADDR_W-1:TAG_POS];


//   logic [           NB_LINE-1:0] hit_bus;
//   logic                          hit;
//   assign hit = |hit_bus;

//   typedef enum {
//     StIdle,
//     StRead,
//     StWrite,
//     StRdWr
//   } access_e;

//   typedef enum {
//     StRdIdle,
//     StRdAddr,
//     StRdData
//   } r_state_e;

//   typedef enum {
//     StWrIdle,
//     StWrAddr,
//     StWrData,
//     StWrBresp
//   } w_state_e;

//   access_e state_q, state_d;
//   r_state_e r_state_q, r_state_d;
//   w_state_e w_state_q, w_state_d;

//   access_e target_state;

//   always_comb begin
//     unique case ({
//       axi_arvalid_i, axi_awvalid_i
//     })
//       2'b00:   target_state = StIdle;
//       2'b10:   target_state = StRead;
//       2'b01:   target_state = StWrite;
//       2'b11:   target_state = StRdWr;
//       default: target_state = StIdle;
//     endcase
//   end

//   always_ff @(posedge clk_i or negedge rst_ni) begin
//     if (!rst_ni) state_q <= StIdle;
//     else state_q <= state_d;
//   end

//   always_comb begin
//     state_d = state_q;

//     unique case (state_q)
//       StIdle: begin
//         state_d = target_state;
//       end

//       StRead: begin
//         if (r_state_q == StRdData) begin
//           state_d = target_state;
//         end
//       end

//       StWrite: begin
//         if (w_state_q == StWrIdle) begin
//           state_d = target_state;
//         end
//       end

//       StRdWr: begin
//         if (r_state_q == StRdData) begin
//           state_d = StWrite;
//         end
//       end

//       default: state_d = StIdle;
//     endcase
//   end


//   always_comb begin
//     unique case (state_q)
//       StRead, StRdWr: begin
//         addr = axi_araddr_i;
//         for (int i = 0; i < NB_LINE; i++) begin
//           hit_bus[i] = (tags[i] == axi_araddr_i[TAG_POS-1:WORD_POS]) && tag_valid[i];
//         end
//       end

//       StWrite: begin
//         addr = axi_awaddr_i;
//         for (int i = 0; i < NB_LINE; i++) begin
//           hit_bus[i] = (tags[i] == axi_awaddr_i[TAG_POS-1:WORD_POS]) && tag_valid[i];
//         end
//       end

//       default: begin
//         addr    = axi_araddr_i;
//         hit_bus = '0;
//       end
//     endcase
//   end

//   always_ff @(posedge clk_i or negedge rst_ni) begin
//     if (!rst_ni) r_state_q <= StRdIdle;
//     else r_state_q <= r_state_d;
//   end

//   always_comb begin
//     r_state_d    = r_state_q;
//     axi_arready_o = 1'b0;
//     axi_rvalid_o  = 1'b0;
//     axi_rresp_o   = 2'b00;

//     unique case (r_state_q)
//       StRdIdle: begin
//         if (hit && (state_q == StRead || state_q == StRdWr)) begin
//           r_state_d = StRdAddr;
//         end
//       end

//       StRdAddr: begin
//         axi_arready_o = 1'b1;
//         if (axi_arready_o && axi_arvalid_i) r_state_d = StRdData;
//       end

//       StRdData: begin
//         axi_rvalid_o = 1'b1;
//         if (axi_rvalid_o && axi_rready_i) r_state_d = StRdIdle;
//       end

//       default: r_state_d = StRdIdle;
//     endcase
//   end


//   always_ff @(posedge clk_i or negedge rst_ni) begin
//     if (!rst_ni) w_state_q <= StWrIdle;
//     else w_state_q <= w_state_d;
//   end

//   always_comb begin
//     w_state_d    = w_state_q;
//     axi_awready_o = 1'b0;
//     axi_wready_o  = 1'b0;
//     axi_bvalid_o  = 1'b0;
//     axi_bresp_o   = 2'b00;

//     unique case (w_state_q)
//       StWrIdle: begin
//         if (hit && state_q == StWrite) begin
//           w_state_d = StWrAddr;
//         end
//       end

//       StWrAddr: begin
//         axi_awready_o = 1'b1;
//         if (axi_awready_o && axi_awvalid_i) w_state_d = StWrData;
//       end

//       StWrData: begin
//         axi_wready_o = 1'b1;
//         if (axi_wready_o && axi_wvalid_i) begin
//           axi_bvalid_o = 1'b1;
//           if (axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
//           else w_state_d = StWrBresp;
//         end
//       end

//       StWrBresp: begin
//         axi_bvalid_o = 1'b1;
//         if (axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
//       end

//       default: w_state_d = StWrIdle;
//     endcase
//   end

//   logic [NbLvl-1:0] binary_way_idx;
//   always_comb begin
//     binary_way_idx = '0;
//     for (int i = 0; i < NB_LINE; i++) begin
//       if (hit_bus[i]) binary_way_idx = NbLvl'(i);
//     end
//   end

//   logic [NbLvl-1:0] lru_way;

//   logic lru_access_ready;
//   logic lru_access_valid;

//   logic lru_way_valid;
//   logic lru_way_ready;

//   plru plru_inst (
//       .clk_i(clk_i),
//       .rst_ni(rst_ni),
//       .access_i(binary_way_idx),
//       .access_valid_i(lru_access_valid),
//       .access_ready_o(lru_access_ready),
//       .lru_way_o(lru_way),
//       .lru_way_valid_o(lru_way_valid),
//       .lru_way_ready_i(lru_way_ready)
//   );

//   typedef enum {
//     StMissIdle,
//     StEvictLine,
//     StFillNewLine,
//     StRefill,
//     StWriteback
//   } miss_e;

//   miss_e miss_d, miss_q;

//   logic [NbLvl-1:0] line_ptr;

//   always_ff @(posedge clk_i or negedge rst_ni) begin
//     if (!rst_ni) begin
//       miss_q <= StMissIdle;

//       line_ptr <= '0;
//       tag_valid <= '0;
//       dirty <= '0;

//       tags <= '{default: '0};
//     end else begin
//       miss_q <= miss_d;

//       if(miss_q == StRefill) begin
//         if(resp_valid_i && resp_data_i == REFILL) begin
//           if(&tag_valid) begin
//             tag_valid[lru_way] <= 1'b1;
//             tags[lru_way] <= addr[TAG_POS-1:WORD_POS];
//             if(state_q == StWrite) dirty[lru_way] <= 1'b1;
//             else dirty[lru_way] <= 1'b0;
//           end else begin
//             line_ptr <= line_ptr + 1'b1;
//             tag_valid[line_ptr] <= 1'b1;
//             tags[line_ptr] <= addr[TAG_POS-1:WORD_POS];
//             if(state_q == StWrite) dirty[line_ptr] <= 1'b1;
//             else dirty[line_ptr] <= 1'b0;
//           end
//         end
//       end
//     end
//   end

//   assign cdc_data_o.nb_transfer = 8'((LINE_SIZE * 8) / MEM_DATA_W);
//   assign cdc_data_o.cache_addr  = {chosen_way, {MemOffset{1'b0}}};

//   always_comb begin
//     miss_d              = miss_q;
//     cdc_valid_o         = 1'b0;
//     cdc_data_o.mem_addr = {{OVERFLOW{1'b0}}, addr[TAG_POS-1:WORD_POS], {WORD_POS{1'b0}}};
//     cdc_data_o.wb_rf    = REFILL;

//     resp_ready_o = 1'b0;

//     lru_access_valid = 1'b0;
//     lru_way_ready = 1'b0;

//     unique case (miss_q)
//       StMissIdle: begin
//         if (!hit && state_q != StIdle) begin
//           if (&tag_valid) begin
//             miss_d = StEvictLine;

//             lru_access_valid = 1'b1;
//             if(lru_access_ready) miss_d = StEvictLine;
//           end
//           else miss_d = StFillNewLine;
//         end
//       end

//       StFillNewLine: begin
//         cdc_valid_o = 1'b1;

//         cdc_data_o.wb_rf = REFILL;
//         cdc_data_o.mem_addr = {{OVERFLOW{1'b0}}, addr[TAG_POS-1:WORD_POS], {WORD_POS{1'b0}}};

//         if (cdc_ready_i) miss_d = StRefill;
//       end

//       StRefill: begin
//         if(resp_valid_i && resp_data_i == REFILL) begin
//           resp_ready_o = 1'b1;
//           miss_d = StMissIdle;
//         end
//       end

//       StEvictLine: begin
//         lru_way_ready = 1'b1;
//         if(lru_way_valid) begin
//           if(dirty[lru_way]) begin
//             cdc_valid_o = 1'b1;

//             cdc_data_o.wb_rf = WRITEBACK;
//             cdc_data_o.mem_addr = {{OVERFLOW{1'b0}}, tags[lru_way], {WORD_POS{1'b0}}};

//             if (cdc_ready_i) miss_d = StWriteback;
//           end else begin
//             cdc_valid_o = 1'b1;

//             cdc_data_o.wb_rf = REFILL;
//             cdc_data_o.mem_addr = {{OVERFLOW{1'b0}}, addr[TAG_POS-1:WORD_POS], {WORD_POS{1'b0}}};

//             if (cdc_ready_i) miss_d = StRefill;
//           end
//         end
//       end

//       StWriteback: begin
//         if(resp_valid_i && resp_data_i == WRITEBACK) begin
//           resp_ready_o = 1'b1;
//           miss_d = StFillNewLine;
//         end
//       end

//       default: ;
//     endcase
//   end

//   logic [NB_TAG-1:0] chosen_way;
//   assign chosen_way = (!(&tag_valid)) ? NB_TAG'(line_ptr) : lru_way;

//   assign ram_addr_o = {binary_way_idx, word};

//   assign axi_rdata_o = ram_data_i;
//   assign ram_data_o  = axi_wdata_i;
//   assign ram_we_o    = (axi_wready_o && axi_wvalid_i) ? axi_wstrb_i : '0;

// endmodule
