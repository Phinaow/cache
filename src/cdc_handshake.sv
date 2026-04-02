module cdc_handshake #(
    parameter type T = logic [31:0]
) (
    input  logic clk_src_i,
    input  logic rst_src_ni,
    input  T     src_data_i,
    input  logic src_valid_i,
    output logic src_ready_o,

    input  logic clk_dst_i,
    input  logic rst_dst_ni,
    output T     dst_data_o,
    output logic dst_valid_o,
    input  logic dst_ready_i
);

  logic src_req_q, src_ack_q;
  logic dst_req_q, dst_ack_q;

  logic temp;

  always_ff @(posedge (clk_src_i) or negedge (rst_src_ni)) begin
    if (!rst_src_ni) begin
      src_req_q <= (1'b0);
    end else begin
      if (src_valid_i && temp && !src_ready_o) begin
        src_req_q <= ~src_req_q;
      end
    end
  end

  always_ff @(posedge (clk_src_i) or negedge (rst_src_ni)) begin
    if (!rst_src_ni) begin
      src_ack_q <= (1'b0);
      src_ready_o <= 1'b0;
    end else begin
      src_ack_q <= (dst_ack_q);

      src_ready_o <= (src_ack_q != dst_ack_q);
    end
  end

  assign temp = (src_req_q == src_ack_q);

  always_ff @(posedge (clk_dst_i) or negedge (rst_dst_ni)) begin
    if (!rst_dst_ni) begin
      dst_ack_q <= (1'b0);
    end else begin
      if (dst_valid_o && dst_ready_i) begin
        dst_ack_q <= ~dst_ack_q;
      end
    end
  end

  always_ff @(posedge (clk_dst_i) or negedge (rst_dst_ni)) begin
    if (!rst_dst_ni) begin
      dst_req_q <= (1'b0);
    end else begin
      dst_req_q <= (src_req_q);
    end
  end

  assign dst_valid_o = (dst_req_q != dst_ack_q);

  assign dst_data_o = src_data_i;

endmodule
