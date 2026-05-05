module plru
  import cache_pkg::*;
#(
    localparam int unsigned NbLvl = (NB_LINE != 1) ? $clog2(NB_LINE) : 1
) (
    input  logic               clk_i,
    input  logic               rst_ni,

    input  logic [NbLvl-1:0] access_i,
    input logic access_valid_i,
    output logic access_ready_o,

    output logic [  NbLvl-1:0] lru_way_o,
    output logic lru_way_valid_o
    // input logic lru_way_ready_i
);

  // typedef enum {
  //   StIdle,
  //   StComputeAccessedNodes,
  //   StComputeLRUTree,
  //   StComputeLRUWay
  // } state_e;

  // state_e state_q, state_d;

  logic [NbLvl-1:0] access;
  logic [NbLvl-1:0] accessed_nodes_d[NbLvl];
  logic [NbLvl-1:0] accessed_nodes_q[NbLvl];
  logic [NbLvl-1:0] shift_accessed_node;

  // logic [  NbLvl-1:0] binary_way_idx;

  logic [NB_LINE-2:0] lru_tree;

  logic [NbLvl-1:0] index [NbLvl];

  // Convert one hot vector to binary
  // always_comb begin
  //   binary_way_idx = '0;
  //   for (int i = 0; i < NB_LINE; i++) begin
  //     if (access[i]) begin
  //       binary_way_idx = i[NbLvl-1:0];
  //     end
  //   end
  // end

  // always_ff @(posedge clk_i or negedge rst_ni) begin
  //   if(!rst_ni) begin
  //     state_q <= StIdle;
  //     access <= '0;
  //     accessed_nodes_q <= '{default: '0};
  //     lru_tree <= '0;
  //   end else begin
  //     state_q <= state_d;

  //     if(access_valid_i && access_ready_o) access <= access_i;

  //     if(state_q == StComputeAccessedNodes) begin
  //       for(int lvl = 0; lvl < NbLvl; lvl++) begin
  //         accessed_nodes_q[lvl] <= accessed_nodes_d[lvl];
  //       end
  //     end

  //     if(state_q == StComputeLRUTree) begin
  //       for (int level = 0; level < NbLvl; level++) begin
  //         lru_tree[accessed_nodes_q[level]] <= !access[NbLvl-1-level];
  //       end
  //     end
  //   end
  // end

  // always_comb begin
  //   state_d = state_q;

  //   access_ready_o = 1'b0;

  //   accessed_nodes_d = '{default: '0};

  //   shift_accessed_node = '0;

  //   index = '{default: '0};
  //   lru_way_o = '0;
  //   lru_way_valid_o = 1'b0;

  //   unique case (state_q)
  //     StIdle: begin
  //       access_ready_o = 1'b1;
  //       if(access_valid_i) state_d = StComputeAccessedNodes;
  //     end

  //     StComputeAccessedNodes: begin
  //       accessed_nodes_d[0] = '0;

  //       for(int level = 0; level < NbLvl-1; level++) begin
  //         shift_accessed_node = (accessed_nodes_d[level] << 1);
  //         if(access[NbLvl-1-level]) accessed_nodes_d[level+1] = shift_accessed_node + 2;
  //         else accessed_nodes_d[level+1] = shift_accessed_node + 1;
  //       end

  //       state_d = StComputeLRUTree;
  //     end

  //     StComputeLRUTree: begin
  //       state_d = StComputeLRUWay;
  //     end

  //     StComputeLRUWay: begin
  //       index[0] = '0;
  //       lru_way_o[NbLvl-1] = lru_tree[0];

  //       for(int lvl = 1; lvl < NbLvl; lvl++) begin
  //         if(lru_tree[index[lvl-1]]) index[lvl] = (index[lvl-1] << 1) + 2;
  //         else index[lvl] = (index[lvl-1] << 1) + 1;

  //         lru_way_o[NbLvl-1-lvl] = lru_tree[index[lvl]];
  //       end

  //       lru_way_valid_o = 1'b1;
  //       if(lru_way_ready_i) state_d = StIdle;
  //     end

  //     default:;
  //   endcase
  // end


  typedef struct packed {
    logic [2:0] valid;
  } state_t;

  state_t q, d;

  always_comb begin
    d = q;
    // access_ready_o = !q.valid[0];

    d.valid[2:1] = q.valid[1:0];

    lru_way_valid_o = !(|d.valid) && !access_valid_i;

    if(access_ready_o && access_valid_i) d.valid[0] = 1'b1;
    else d.valid[0] = 1'b0;

    // ====================================Compute Accessed Nodes===================================
    accessed_nodes_d[0] = '0;
    for(int level = 0; level < NbLvl-1; level++) begin
      shift_accessed_node = (accessed_nodes_d[level] << 1);
      if(access[NbLvl-1-level]) accessed_nodes_d[level+1] = shift_accessed_node + 2;
      else accessed_nodes_d[level+1] = shift_accessed_node + 1;
    end

    // =======================================Compute LRU Way=======================================
    index[0] = '0;
    lru_way_o[NbLvl-1] = lru_tree[0];
    for(int lvl = 1; lvl < NbLvl; lvl++) begin
      if(lru_tree[index[lvl-1]]) index[lvl] = (index[lvl-1] << 1) + 2;
      else index[lvl] = (index[lvl-1] << 1) + 1;
      lru_way_o[NbLvl-1-lvl] = lru_tree[index[lvl]];
    end

  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if(!rst_ni) begin
      access <= '0;
      accessed_nodes_q <= '{default: '0};
      lru_tree <= '0;

      q <= '0;
    end else begin
      q <= d;

      if(access_ready_o && access_valid_i) access <= access_i;
      access_ready_o <= !(access_ready_o && access_valid_i);

      // ====================================Set accessed nodes=====================================
      if(q.valid[1]) begin
        for(int lvl = 0; lvl < NbLvl; lvl++) begin
          accessed_nodes_q[lvl] <= accessed_nodes_d[lvl];
        end
      end

      // ========================================Tree Update========================================
      if(q.valid[2]) begin
        for (int level = 0; level < NbLvl; level++) begin
          lru_tree[accessed_nodes_q[level]] <= !access[NbLvl-1-level];
        end
      end

    end
  end

endmodule
