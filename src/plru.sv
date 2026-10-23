module plru
  import cache_pkg::*;
#(
    parameter int unsigned WAYS = NB_LINE,
    localparam int unsigned NbLvl = (WAYS > 1) ? $clog2(WAYS) : 1
) (
    input  logic clk_i,
    input  logic rst_ni,
    input  logic [NbLvl-1:0] access_i,
    input  logic access_valid_i,
    output logic access_ready_o,
    output logic [NbLvl-1:0] lru_way_o,
    output logic lru_way_valid_o
);
  localparam int unsigned TREE_BITS = (WAYS > 1) ? WAYS - 1 : 1;
  logic [TREE_BITS-1:0] tree_q;

  initial begin
    assert (WAYS > 0 && (WAYS & (WAYS - 1)) == 0)
      else $fatal(1, "PLRU requires a positive power-of-two way count");
  end

  assign access_ready_o = rst_ni;
  assign lru_way_valid_o = rst_ni;

  // Each node points to the less recently used subtree.
  always_comb begin
    int unsigned node;
    node = 0;
    lru_way_o = '0;
    if (WAYS > 1) begin
      for (int level = 0; level < NbLvl; level++) begin
        lru_way_o[NbLvl-1-level] = tree_q[node];
        node = 2 * node + 1 + int'(tree_q[node]);
      end
    end
  end

  // Update the entire path at one edge: no pipeline context can be overwritten.
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      tree_q <= '0;
    end else if (access_valid_i && access_ready_o && WAYS > 1) begin
      int unsigned node;
      node = 0;
      for (int level = 0; level < NbLvl; level++) begin
        tree_q[node] <= !access_i[NbLvl-1-level];
        node = 2 * node + 1 + int'(access_i[NbLvl-1-level]);
      end
    end
  end
endmodule
