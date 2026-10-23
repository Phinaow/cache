module hit_detection
  import cache_pkg::*;
(
    input logic clk_i,
    input logic rst_ni,

    input logic                awvalid_i,
    input logic [TAG_SIZE-1:0] awaddr_i,
    input logic                arvalid_i,
    input logic [TAG_SIZE-1:0] araddr_i,

    input logic access_done_i,
    input logic write_commit_i,
    input logic [NB_TAG-1:0] commit_way_i,
    output logic [1:0] lookup_status_o,
    output logic hit_o,
    output logic [NB_TAG-1:0] hit_addr_o,

    output logic [NB_TAG-1:0] access_data_o,
    output logic access_valid_o,
    input logic access_ready_i,

    input logic              lru_way_valid_i,
    input logic [NB_TAG-1:0] lru_way_data_i,

    output logic cdc_req_valid_o,
    output cdc_data_t cdc_req_data_o,
    input logic cdc_req_ready_i,

    input  logic cdc_resp_valid_i,
    input cache_resp_t cdc_resp_data_i,
    output logic cdc_resp_ready_o
);

  typedef enum logic [2:0] {Idle, SendWriteback, WaitWriteback, SendRefill, WaitRefill, Error} state_t;
  state_t state_q;
  logic [TAG_SIZE-1:0] tags_q [NB_LINE];
  logic [NB_LINE-1:0] valid_q, dirty_q;
  logic [TAG_SIZE-1:0] requested_tag, new_tag_q, old_tag_q;
  logic [NB_TAG-1:0] hit_way, victim_way, victim_q;
  logic found, free_found, request;

  assign request = arvalid_i || awvalid_i;
  assign requested_tag = arvalid_i ? araddr_i : awaddr_i;

  always_comb begin
    found = 1'b0;
    free_found = 1'b0;
    hit_way = '0;
    victim_way = lru_way_data_i;
    for (int way = NB_LINE - 1; way >= 0; way--) begin
      if (valid_q[way] && tags_q[way] == requested_tag) begin
        found = 1'b1;
        hit_way = NB_TAG'(way);
      end
      if (!valid_q[way]) begin
        free_found = 1'b1;
        victim_way = NB_TAG'(way);
      end
    end
  end

  assign hit_o = rst_ni && request && ((state_q == Idle && found) || state_q == Error);
  assign hit_addr_o = state_q == Error ? victim_q : hit_way;
  assign lookup_status_o = state_q == Error ? AXI_SLVERR : AXI_OKAY;
  assign access_valid_o = rst_ni && access_done_i;
  assign access_data_o = commit_way_i;
  assign cdc_req_valid_o = rst_ni && (state_q == SendWriteback || state_q == SendRefill);
  assign cdc_req_data_o.wb_rf = state_q == SendWriteback ? WRITEBACK : REFILL;
  assign cdc_req_data_o.mem_addr = MEM_ADDR_W'({
      (state_q == SendWriteback ? old_tag_q : new_tag_q), {WORD_POS{1'b0}}});
  assign cdc_req_data_o.nb_transfer = 8'(LINE_SIZE / (MEM_DATA_W / 8) - 1);
  assign cdc_req_data_o.cache_addr = MEM_CACHE_ADDR_W'(int'(victim_q) * (MEM_CACHE_SIZE / NB_LINE));
  assign cdc_resp_ready_o = rst_ni && (state_q == WaitWriteback || state_q == WaitRefill);

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q <= Idle;
      tags_q <= '{default: '0};
      valid_q <= '0;
      dirty_q <= '0;
      victim_q <= '0;
      new_tag_q <= '0;
      old_tag_q <= '0;
    end else begin
      if (write_commit_i) dirty_q[commit_way_i] <= 1'b1;
      // The connected PLRU accepts every commit. Do not silently drop an event.
      assert (!access_done_i || access_ready_i)
        else $fatal(1, "Replacement policy did not accept a completed access");
      case (state_q)
        Idle: if (request && !found && (free_found || lru_way_valid_i)) begin
          victim_q <= victim_way;
          new_tag_q <= requested_tag;
          old_tag_q <= tags_q[victim_way];
          if (valid_q[victim_way] && dirty_q[victim_way]) state_q <= SendWriteback;
          else begin
            // A partial refill must never leave an old tag pointing at new data.
            valid_q[victim_way] <= 1'b0;
            dirty_q[victim_way] <= 1'b0;
            state_q <= SendRefill;
          end
        end
        SendWriteback: if (cdc_req_ready_i) state_q <= WaitWriteback;
        WaitWriteback: if (cdc_resp_valid_i) begin
          if (cdc_resp_data_i.status != AXI_OKAY || cdc_resp_data_i.wb_rf != WRITEBACK)
            state_q <= Error;
          else begin
            valid_q[victim_q] <= 1'b0;
            dirty_q[victim_q] <= 1'b0;
            state_q <= SendRefill;
          end
        end
        SendRefill: if (cdc_req_ready_i) state_q <= WaitRefill;
        WaitRefill: if (cdc_resp_valid_i) begin
          if (cdc_resp_data_i.status != AXI_OKAY || cdc_resp_data_i.wb_rf != REFILL) state_q <= Error;
          else begin
            tags_q[victim_q] <= new_tag_q;
            valid_q[victim_q] <= 1'b1;
            dirty_q[victim_q] <= 1'b0;
            state_q <= Idle;
          end
        end
        Error: if (!request) state_q <= Idle;
        default: state_q <= Idle;
      endcase
    end
  end
endmodule
