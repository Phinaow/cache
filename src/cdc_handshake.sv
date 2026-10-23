// Single-entry asynchronous mailbox. Either reset cancels the pending transfer
// in both domains. Reset assertion is asynchronous; release is local and delayed.
module cdc_handshake #(
    parameter type T = logic [31:0]
) (
    input  logic clk_src_i,
    input  logic rst_src_ni,
    input  T src_data_i,
    input  logic src_valid_i,
    output logic src_ready_o,
    input  logic clk_dst_i,
    input  logic rst_dst_ni,
    output T dst_data_o,
    output logic dst_valid_o,
    input  logic dst_ready_i
);
  wire reset_ni = rst_src_ni && rst_dst_ni;
  (* ASYNC_REG = "TRUE" *) logic [1:0] source_run_q, destination_run_q;
  (* ASYNC_REG = "TRUE" *) logic [1:0] request_sync_q, acknowledge_sync_q;
  logic request_q, acknowledge_q;
  T source_data_q;

  always_ff @(posedge clk_src_i or negedge reset_ni) begin
    if (!reset_ni) begin
      source_run_q <= '0;
      acknowledge_sync_q <= '0;
    end else begin
      source_run_q <= {source_run_q[0], 1'b1};
      acknowledge_sync_q <= {acknowledge_sync_q[0], acknowledge_q};
    end
  end

  assign src_ready_o = reset_ni && source_run_q[1] &&
                       (request_q == acknowledge_sync_q[1]);

  always_ff @(posedge clk_src_i or negedge reset_ni) begin
    if (!reset_ni) begin
      request_q <= 1'b0;
      source_data_q <= '0;
    end else if (src_valid_i && src_ready_o) begin
      source_data_q <= src_data_i;
      request_q <= !request_q;
    end
  end

  always_ff @(posedge clk_dst_i or negedge reset_ni) begin
    if (!reset_ni) begin
      destination_run_q <= '0;
      request_sync_q <= '0;
    end else begin
      destination_run_q <= {destination_run_q[0], 1'b1};
      request_sync_q <= {request_sync_q[0], request_q};
    end
  end

  // The source holds the complete bus until the synchronized acknowledgement.
  // The request has crossed two flops before the destination captures the bus.
  always_ff @(posedge clk_dst_i or negedge reset_ni) begin
    if (!reset_ni) begin
      acknowledge_q <= 1'b0;
      dst_data_o <= '0;
      dst_valid_o <= 1'b0;
    end else if (destination_run_q[1]) begin
      if (!dst_valid_o && request_sync_q[1] != acknowledge_q) begin
        dst_data_o <= source_data_q;
        dst_valid_o <= 1'b1;
      end else if (dst_valid_o && dst_ready_i) begin
        dst_valid_o <= 1'b0;
        acknowledge_q <= request_sync_q[1];
      end
    end
  end
endmodule
