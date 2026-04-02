module plru
  import cache_pkg::*;
#(
    localparam int unsigned NbLvl = $clog2(NB_LINE)
) (
    input  logic               clk_i,
    input  logic               rst_ni,
    input  logic [NB_LINE-1:0] access_i,
    output logic [  NbLvl-1:0] lru_way_o
);

  logic [NB_LINE-2:0] plru_tree;

  logic [  NbLvl-1:0] binary_way_idx;

  typedef logic [NbLvl-1:0] index_array_t[NbLvl];

  function automatic index_array_t get_plru_path(logic [NbLvl-1:0] way_idx);
    logic [NbLvl-1:0] current_node = 0;
    for (int level = 0; level < NbLvl; level++) begin
      get_plru_path[level] = current_node;
      if (way_idx[NbLvl-1-level]) current_node = 2 * current_node + 2;
      else current_node = 2 * current_node + 1;
    end
  endfunction

  always_comb begin
    binary_way_idx = '0;
    for (int i = 0; i < NB_LINE; i++) begin
      if (access_i[i]) begin
        binary_way_idx = i[NbLvl-1:0];
      end
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      plru_tree <= '0;
    end else if (|access_i) begin
      automatic index_array_t path = get_plru_path(binary_way_idx);

      for (int level = 0; level < NbLvl; level++) begin
        plru_tree[path[level]] <= !binary_way_idx[NbLvl-1-level];
      end
    end
  end

  always_comb begin
    automatic index_array_t path = get_plru_path(binary_way_idx);
    for (int level = 0; level < NbLvl; level++) begin
      lru_way_o[level] = plru_tree[path[level]];
    end
  end

endmodule
