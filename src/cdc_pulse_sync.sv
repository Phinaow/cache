module cdc_pulse_sync (
    input  logic clk_src_i,
    input  logic rst_src_ni,
    input  logic pulse_i,
    input  logic clk_dst_i,
    input  logic rst_dst_ni,
    output logic pulse_o
);
  logic toggle_src;
  logic [2:0] sync_dst;

  always_ff @(posedge clk_src_i or negedge rst_src_ni) begin
    if (!rst_src_ni) begin
      toggle_src <= 1'b0;
    end else if (pulse_i) begin
      toggle_src <= ~toggle_src;
    end
  end

  always_ff @(posedge clk_dst_i or negedge rst_dst_ni) begin
    if (!rst_dst_ni) begin
      sync_dst <= 3'b0;
    end else begin
      sync_dst <= {sync_dst[1:0], toggle_src};
    end
  end

  assign pulse_o = sync_dst[2] ^ sync_dst[1];
endmodule
