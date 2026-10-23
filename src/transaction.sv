module transaction
  import cache_pkg::*;
(
    input  logic                  clk_i,
    input  logic                  rst_ni,
    // ----------------- //
    // Write AXI signals
    // ----------------- //
    input  logic [CPU_ADDR_W-1:0] axi_awaddr_i,
    input  logic                  axi_awvalid_i,
    output logic                  axi_awready_o,
    // Data signals
    input  logic [CPU_DATA_W-1:0] axi_wdata_i,
    input  logic                  axi_wvalid_i,
    output logic                  axi_wready_o,
    input  logic [CPU_DATA_W/8-1:0] axi_wstrb_i,
    // Response signals
    output logic [           1:0] axi_bresp_o,
    output logic                  axi_bvalid_o,
    input  logic                  axi_bready_i,
    // ---------------- //
    // Read AXI signals
    // ---------------- //
    input  logic [CPU_ADDR_W-1:0] axi_araddr_i,
    input  logic                  axi_arvalid_i,
    output logic                  axi_arready_o,
    // Data signals
    output logic [CPU_DATA_W-1:0] axi_rdata_o,
    output logic [           1:0] axi_rresp_o,
    output logic                  axi_rvalid_o,
    input  logic                  axi_rready_i,

    // Hit detection signals
    output logic [TAG_SIZE-1:0] awaddr_o,
    output logic                awvalid_o,

    output logic [TAG_SIZE-1:0] araddr_o,
    output logic                arvalid_o,

    input logic hit_i,
    input logic [1:0] lookup_status_i,
    output logic access_done_o,
    output logic write_commit_o,
    output logic [NB_TAG-1:0] commit_way_o,
    input logic [NB_TAG-1:0] hit_addr_i,

    // True dual port signals
    output logic [CPU_CACHE_ADDR_W-1:0] ram_addr_o,
    output logic ram_en_o,
    output logic [      CPU_DATA_W-1:0] ram_data_o,
    input  logic [      CPU_DATA_W-1:0] ram_data_i,
    output logic [  (CPU_DATA_W/8)-1:0] ram_we_o
);

  typedef enum logic [2:0] {
    Idle, ReadLookup, ReadWait, ReadCapture, ReadResponse,
    WriteLookup, WriteCommit, WriteResponse
  } state_t;
  state_t state_q;
  logic aw_pending_q, w_pending_q, ar_pending_q;
  logic [CPU_ADDR_W-1:0] aw_address_q, ar_address_q, address_q;
  logic [CPU_DATA_W-1:0] write_data_q, data_q;
  logic [CPU_DATA_W/8-1:0] write_strobe_q, strobe_q;
  logic [NB_TAG-1:0] way_q;
  logic prefer_write_q;
  logic read_active, write_active;

  function automatic logic address_valid(input logic [CPU_ADDR_W-1:0] address);
    return address < CPU_ADDR_W'(MEM_SIZE) && address[OFFSET_POS-1:0] == '0;
  endfunction

  assign read_active = state_q == ReadLookup || state_q == ReadWait ||
                       state_q == ReadCapture || state_q == ReadResponse;
  assign write_active = state_q == WriteLookup || state_q == WriteCommit || state_q == WriteResponse;
  assign axi_awready_o = rst_ni && !aw_pending_q && !write_active;
  assign axi_wready_o = rst_ni && !w_pending_q && !write_active;
  assign axi_arready_o = rst_ni && !ar_pending_q && !read_active;
  assign axi_rvalid_o = rst_ni && state_q == ReadResponse;
  assign axi_bvalid_o = rst_ni && state_q == WriteResponse;
  assign arvalid_o = rst_ni && state_q == ReadLookup;
  assign awvalid_o = rst_ni && state_q == WriteLookup;
  assign araddr_o = address_q[TAG_POS-1:WORD_POS];
  assign awaddr_o = address_q[TAG_POS-1:WORD_POS];
  assign ram_addr_o = CPU_CACHE_ADDR_W'({way_q, address_q[WORD_POS-1:OFFSET_POS]});
  assign ram_data_o = data_q;
  assign ram_en_o = (state_q == ReadWait || state_q == ReadCapture || state_q == WriteCommit);
  assign ram_we_o = state_q == WriteCommit ? strobe_q : '0;
  assign access_done_o = rst_ni && (state_q == ReadCapture || state_q == WriteCommit);
  assign write_commit_o = rst_ni && state_q == WriteCommit;
  assign commit_way_o = way_q;

  // RAM address/data/control registers reset synchronously. Reset may discard
  // cached data, but must not move a BRAM address between clock edges.
  always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
      state_q <= Idle;
      aw_pending_q <= 1'b0;
      w_pending_q <= 1'b0;
      ar_pending_q <= 1'b0;
      aw_address_q <= '0;
      ar_address_q <= '0;
      address_q <= '0;
      write_data_q <= '0;
      data_q <= '0;
      write_strobe_q <= '0;
      strobe_q <= '0;
      way_q <= '0;
      prefer_write_q <= 1'b0;
      axi_rdata_o <= '0;
      axi_rresp_o <= AXI_OKAY;
      axi_bresp_o <= AXI_OKAY;
    end else begin
      // AW and W are independent AXI channels, each with one holding register.
      if (axi_awvalid_i && axi_awready_o) begin
        aw_pending_q <= 1'b1;
        aw_address_q <= axi_awaddr_i;
      end
      if (axi_wvalid_i && axi_wready_o) begin
        w_pending_q <= 1'b1;
        write_data_q <= axi_wdata_i;
        write_strobe_q <= axi_wstrb_i;
      end
      if (axi_arvalid_i && axi_arready_o) begin
        ar_pending_q <= 1'b1;
        ar_address_q <= axi_araddr_i;
      end

      case (state_q)
        Idle: begin
          if (ar_pending_q && (!(aw_pending_q && w_pending_q) || !prefer_write_q)) begin
            address_q <= ar_address_q;
            ar_pending_q <= 1'b0;
            prefer_write_q <= 1'b1;
            axi_rresp_o <= address_valid(ar_address_q) ? AXI_OKAY : AXI_SLVERR;
            if (address_valid(ar_address_q)) state_q <= ReadLookup;
            else begin
              axi_rdata_o <= '0;
              state_q <= ReadResponse;
            end
          end else if (aw_pending_q && w_pending_q) begin
            address_q <= aw_address_q;
            data_q <= write_data_q;
            strobe_q <= write_strobe_q;
            aw_pending_q <= 1'b0;
            w_pending_q <= 1'b0;
            prefer_write_q <= 1'b0;
            axi_bresp_o <= address_valid(aw_address_q) ? AXI_OKAY : AXI_SLVERR;
            if (!address_valid(aw_address_q) || write_strobe_q == '0) state_q <= WriteResponse;
            else state_q <= WriteLookup;
          end
        end
        ReadLookup: if (hit_i) begin
          way_q <= hit_addr_i;
          axi_rresp_o <= lookup_status_i;
          if (lookup_status_i == AXI_OKAY) state_q <= ReadWait;
          else begin
            axi_rdata_o <= '0;
            state_q <= ReadResponse;
          end
        end
        // Give the synchronous RAM a complete cycle at the selected address.
        ReadWait: state_q <= ReadCapture;
        ReadCapture: begin
          axi_rdata_o <= ram_data_i;
          state_q <= ReadResponse;
        end
        ReadResponse: if (axi_rready_i) state_q <= Idle;
        WriteLookup: if (hit_i) begin
          way_q <= hit_addr_i;
          axi_bresp_o <= lookup_status_i;
          state_q <= lookup_status_i == AXI_OKAY ? WriteCommit : WriteResponse;
        end
        WriteCommit: state_q <= WriteResponse;
        WriteResponse: if (axi_bready_i) state_q <= Idle;
        default: state_q <= Idle;
      endcase
    end
  end
endmodule
