module hit_detection
  import cache_pkg::*;
(
    input logic clk_i,
    input logic rst_ni,

    input logic                awvalid_i,
    input logic [TAG_SIZE-1:0] awaddr_i,
    input logic                arvalid_i,
    input logic [TAG_SIZE-1:0] araddr_i,

    output logic hit_o,
    output logic [NB_TAG-1:0] hit_addr_o,

    output logic [NB_TAG-1:0] access_data_o,
    output logic access_valid_o,
    input logic access_ready_i,

    input logic              lru_way_valid_i,
    input logic [NB_TAG-1:0] lru_way_data_i,
    // output logic lru_way_ready_o,

    output logic cdc_req_valid_o,
    output cdc_data_t cdc_req_data_o,
    input logic cdc_req_ready_i,

    input  logic cdc_resp_valid_i,
    // input rf_wb_e cdc_rsp_data_i,
    output logic cdc_resp_ready_o
);

  localparam int MemOffset = $clog2(MEM_CACHE_SIZE / NB_LINE);

  logic [NB_LINE-1:0] hit_bus;
  logic               hit;

  assign hit = |hit_bus;

  logic [TAG_SIZE-1:0] addr;

  logic [TAG_SIZE-1:0] tags      [NB_LINE];
  logic [ NB_LINE-1:0] tag_valid;
  logic [ NB_LINE-1:0] dirty;

  typedef struct packed {
    logic need_rf;
    logic need_wb;
    logic use_lru;
    logic use_cnt;
    logic write;
    // logic read;
    // logic valid;
  } state_t;

  state_t q, d;

  typedef enum {
    StIdle,
    StSendReq,
    StWaitResp
  } miss_e;

  miss_e miss_q, miss_d;

  logic [NB_TAG-1:0] cnt;

  logic [NB_TAG-1:0] lru_way;

  logic access;
  assign access = arvalid_i | awvalid_i;

  logic [NB_TAG-1:0] chosen_way;
  assign chosen_way = (&tag_valid) ? lru_way : NB_TAG'(cnt);

  logic complete_access;

  assign cdc_req_data_o.nb_transfer = 8'((LINE_SIZE * 8) / MEM_DATA_W) - 1;

  always_comb begin

    d = q;

    // cdc_req_data_o.nb_transfer = 8'((LINE_SIZE * 8) / MEM_DATA_W) - 1;

    cdc_req_valid_o = 1'b0;
    cdc_resp_ready_o = 1'b0;

    // ========================================Hit detection========================================

    casez ({
      arvalid_i, awvalid_i
    })
      2'b1?: begin
        addr = araddr_i;
        for (int i = 0; i < NB_LINE; i++) begin
          hit_bus[i] = (tags[i] == araddr_i) && tag_valid[i];
        end
        // d.read = 1'b1;
      end

      2'b01: begin
        addr = awaddr_i;
        for (int i = 0; i < NB_LINE; i++) begin
          hit_bus[i] = (tags[i] == awaddr_i) && tag_valid[i];
        end
        d.write = 1'b1;
      end

      default: begin
        addr    = araddr_i;
        hit_bus = '0;
        d = '0;
      end
    endcase

    // =======================================Access with miss======================================

    cdc_req_data_o.mem_addr = {{OVERFLOW{1'b0}}, addr, {WORD_POS{1'b0}}};
    cdc_req_data_o.wb_rf = REFILL;
    cdc_req_data_o.cache_addr = {chosen_way, {MemOffset{1'b0}}};

    miss_d = miss_q;

    access_valid_o = 1'b0;

    unique case (miss_q)
      StIdle: begin
        d = '0;
        if (!hit && access) begin
          if (&tag_valid) d.use_lru = 1'b1;
          else d.use_cnt = 1'b1;

          miss_d = StSendReq;
        end

        if (hit && access && access_ready_i) begin
          access_valid_o = !complete_access;  // 1'b1;
        end
      end

      StSendReq: begin
        if (q.use_lru && dirty[lru_way]) begin
          d.need_wb = 1'b1;

          cdc_req_data_o.wb_rf = WRITEBACK;
          cdc_req_data_o.mem_addr = {{OVERFLOW{1'b0}}, tags[lru_way], {WORD_POS{1'b0}}};

        end else begin
          d.need_rf = 1'b1;
        end

        cdc_req_valid_o = 1'b1;
        if (cdc_req_ready_i && cdc_req_valid_o) miss_d = StWaitResp;
      end

      StWaitResp: begin
        cdc_resp_ready_o = 1'b1;
        if (cdc_resp_ready_o && cdc_resp_valid_i) begin
          if (q.need_wb) begin
            d.need_wb = 1'b0;
            miss_d = StSendReq;
          end

          if (q.need_rf) begin
            d.need_rf = 1'b0;
            miss_d = StIdle;
          end
        end
      end

      default: ;
    endcase

  end

  logic refill_done;
  logic [NB_TAG-1:0] binary_way_idx;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      dirty <= '0;
      tag_valid <= '0;
      tags <= '{default: '0};
      cnt <= '0;
      lru_way <= '0;

      complete_access <= 1'b0;

      q <= '0;

      refill_done <= 1'b0;

      miss_q <= StIdle;
    end else begin

      q <= d;

      miss_q <= miss_d;

      if(refill_done) refill_done <= 1'b0;

      if (access_ready_i && access_valid_o) complete_access <= 1'b1;
      if (miss_q != StIdle) complete_access <= 1'b0;

      if (miss_q == StWaitResp) begin
        if (cdc_resp_ready_o && cdc_resp_valid_i) begin
          if (q.need_wb) dirty[lru_way] <= 1'b0;

          if (q.need_rf) begin
            refill_done <= 1'b1;
            if (q.use_lru) begin
              tags[lru_way] <= addr;
              // if (q.write) dirty[lru_way] <= 1'b1;
              // else dirty[lru_way] <= 1'b0;
              dirty[lru_way] <= 1'b0;
            end

            if (q.use_cnt) begin
              tags[cnt] <= addr;
              cnt <= cnt + 1'b1;
              tag_valid[cnt] <= 1'b1;
              // if (q.write) dirty[cnt] <= 1'b1;
              // else dirty[cnt] <= 1'b0;
              dirty[cnt] <= 1'b0;
            end
          end
        end
      end

      if(awvalid_i && hit_o) begin
        dirty[binary_way_idx] <= 1'b1;
      end

      if (lru_way_valid_i) lru_way <= lru_way_data_i;

    end
  end

  // ======================Transform one hot encoded vector to his binary value=====================

  always_comb begin
    binary_way_idx = '0;
    for (int i = 0; i < NB_LINE; i++) begin
      if (hit_bus[i]) binary_way_idx = NB_TAG'(i);
    end
  end

  // logic [WORD_SIZE-1:0] word;

  // assign word          = addr[WORD_POS-1:OFFSET_POS];

  assign hit_addr_o    = binary_way_idx;  // {binary_way_idx, word};

  assign access_data_o = binary_way_idx;

  assign hit_o         = hit && access && !refill_done;  // access_ready_i;

endmodule
