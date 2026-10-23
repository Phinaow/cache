// Asynchronous assertion, two-edge synchronous release in the local domain.
module reset_sync (
    input logic clk_i,
    input logic rst_ni,
    output logic rst_no
);
  (* ASYNC_REG = "TRUE" *) logic [1:0] release_q;
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) release_q <= '0;
    else release_q <= {release_q[0], 1'b1};
  end
  // Drive consumers directly from the final flop. A combinational AND with
  // the raw reset would reintroduce an unsynchronized path to every consumer.
  assign rst_no = release_q[1];
endmodule
