module cache_controller
  import cache_pkg::*;
(
    input  logic                  clk_i,
    input  logic                  rst_ni,
    // ----------------- //
    // Write AXI signals
    // ----------------- //
    // Config signals
    input  logic [CPU_ADDR_W-1:0] axi_awaddr_i,
    input  logic                  axi_awvalid_i,
    output logic                  axi_awready_o,
    // Data signals
    input  logic [CPU_DATA_W-1:0] axi_wdata_i,
    input  logic                  axi_wvalid_i,
    output logic                  axi_wready_o,
    input  logic [           3:0] axi_wstrb_i,
    // Response signals
    output logic [           1:0] axi_bresp_o,
    output logic                  axi_bvalid_o,
    input  logic                  axi_bready_i,
    // ---------------- //
    // Read AXI signals
    // ---------------- //
    // Config signals
    input  logic [CPU_ADDR_W-1:0] axi_araddr_i,
    input  logic                  axi_arvalid_i,
    output logic                  axi_arready_o,
    // Data signals
    output logic [CPU_DATA_W-1:0] axi_rdata_o,
    output logic [           1:0] axi_rresp_o,
    output logic                  axi_rvalid_o,
    input  logic                  axi_rready_i,


    output logic [CPU_CACHE_ADDR_W-1:0] ram_addr_o,
    output logic [      CPU_DATA_W-1:0] ram_data_o,
    input  logic [      CPU_DATA_W-1:0] ram_data_i,
    output logic [  (CPU_DATA_W/8)-1:0] ram_we_o,

    output cdc_data_t cdc_data_o,
    output logic      cdc_valid_o,
    input  logic      cdc_ready_i
);

  logic [TAG_SIZE-1:0] tags[NB_LINE];
  logic [NB_LINE-1:0] tag_valid;
  logic [NB_LINE-1:0] dirty;
  logic [WORD_SIZE-1:0] word;
  logic [OFFSET_SIZE-1:0] offset;  // Will be used to detect a non alignment
  logic [CPU_ADDR_W-1-TAG_POS:0] overflow;  // Will be used to detect extra access (counter)

  logic [CPU_ADDR_W-1:0] addr;
  logic [NB_LINE-1:0] hit_bus;
  logic hit;

  // TEMPORARY DEBUG \\

  // assign axi_bvalid_o = 1'b1;
  // assign axi_rvalid_o = 1'b1;



  assign hit = |hit_bus;

  typedef enum {
    StIdle,
    StRead,
    StWrite,
    StRdWr
  } access_e;

  typedef enum {
    StRdIdle,
    StRdAddr,
    StRdData
  } r_state_e;

  typedef enum {
    StWrIdle,
    StWrAddr,
    StWrData,
    StWrBresp
  } w_state_e;

  r_state_e r_state_q, r_state_d;
  w_state_e w_state_q, w_state_d;

  access_e state_q, state_d;

  // Access FSM
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q <= StIdle;
    end
    begin
      state_q <= state_d;
    end
  end

  access_e target_state;

  always_comb begin
    unique case ({
      axi_arvalid_i, axi_awvalid_i
    })
      2'b00:   target_state = StIdle;
      2'b10:   target_state = StRead;
      2'b01:   target_state = StWrite;
      2'b11:   target_state = StRdWr;
      default: target_state = StIdle;
    endcase
  end

  // Access arbitrator
  always_comb begin
    state_d = state_q;

    unique case (state_q)
      StIdle: begin
        state_d = target_state;
      end

      StRead: begin
        if (r_state_q == StRdData) begin
          state_d = target_state;
        end
      end

      StWrite: begin
        if (w_state_q == StWrIdle) begin
          state_d = target_state;
        end
      end

      StRdWr: begin
        if (r_state_q == StRdData) begin
          state_d = StWrite;
        end
      end

      default: state_d = StIdle;
    endcase
  end

  // hit detection
  always_comb begin

    case (state_d)
      StRead, StRdWr: begin
        addr = axi_araddr_i;
        for (int i = 0; i < NB_LINE; i++) begin
          hit_bus[i] = (tags[i] == axi_araddr_i[TAG_POS-1:WORD_POS]) && tag_valid[i];
        end
      end

      StWrite: begin
        addr = axi_awaddr_i;
        for (int i = 0; i < NB_LINE; i++) begin
          hit_bus[i] = (tags[i] == axi_awaddr_i[TAG_POS-1:WORD_POS]) && tag_valid[i];
        end
      end

      default: begin
        addr = axi_araddr_i;
        hit_bus = '0;
      end
    endcase
  end

  assign word = addr[WORD_POS-1:OFFSET_POS];
  assign offset = addr[OFFSET_POS-1:0];
  assign overflow = addr[CPU_ADDR_W-1:TAG_POS];

  logic [ NB_TAG-1:0] line_ptr;

  logic [ NB_TAG-1:0] lru_way;
  logic [NB_LINE-1:0] plru_access;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      // miss_corrected <= 1'b0;
      // need_writeback <= 1'b0;
    end else begin
      // miss_corrected <= 1'b0;
      if (!hit && state_q != StIdle) begin
        if (!&tag_valid) begin
          if (cdc_ready_i && cdc_valid_o) begin
            tags[line_ptr] <= addr[TAG_POS-1:WORD_POS];
            tag_valid[line_ptr] <= 1'b1;
            line_ptr <= line_ptr + 1'b1;
          end
          if (state_q == StWrite) dirty[line_ptr] <= 1'b1;
        end else begin
          if (dirty[lru_way]) begin
            // need_writeback <= 1'b1;

            if (cdc_ready_i && cdc_valid_o) begin
              dirty[lru_way] <= 1'b0;
            end
          end else begin
            // need_writeback <= 1'b0;
            if (cdc_ready_i && cdc_valid_o) begin
              tags[lru_way] <= addr[TAG_POS-1:WORD_POS];
              tag_valid[lru_way] <= 1'b1;
              if (state_q == StWrite) dirty[lru_way] <= 1'b1;
            end
          end
        end
      end else if (hit && state_q != StIdle) begin
        if (state_q == StWrite) dirty <= dirty | hit_bus;
      end
    end
  end


  localparam int MemOffset = $clog2(MEM_CACHE_SIZE / NB_LINE);


  logic [NB_TAG-1:0] chosen_way;
  assign chosen_way = (!(&tag_valid)) ? line_ptr : lru_way;

  assign cdc_data_o.cache_addr = {chosen_way, {MemOffset{1'b0}}};

  // assign need_writeback = &tag_valid && dirty[lru_way];

  always_comb begin

    cdc_data_o.wb_rf = REFILL;
    cdc_valid_o = 1'b0;

    cdc_data_o.mem_addr = {{OVERFLOW{1'b0}}, addr[TAG_POS-1:WORD_POS], {WORD_POS{1'b0}}};
    cdc_data_o.nb_transfer = 8'((LINE_SIZE * 8) / MEM_DATA_W);

    // if(!&tag_valid) cdc_data_o.cache_addr = MEM_CACHE_ADDR_W'((MEM_CACHE_SIZE/NB_LINE) * line_ptr);
    // else cdc_data_o.cache_addr = MEM_CACHE_ADDR_W'((MEM_CACHE_SIZE/NB_LINE) * lru_way);

    if (!hit && state_d != StIdle) begin
      if (!&tag_valid) begin
        cdc_data_o.wb_rf = REFILL;
        cdc_valid_o = 1'b1;
      end else begin
        if (dirty[lru_way]) cdc_data_o.wb_rf = WRITEBACK;
        else cdc_data_o.wb_rf = REFILL;

        if (dirty[lru_way]) begin
          cdc_data_o.mem_addr = {{OVERFLOW{1'b0}}, tags[lru_way], {WORD_POS{1'b0}}};
        end

        cdc_valid_o = 1'b1;
      end
    end
  end

  localparam int unsigned NbLvl = $clog2(NB_LINE);
  logic [NbLvl-1:0] binary_way_idx;

  always_comb begin
    binary_way_idx = '0;
    for (int i = 0; i < NB_LINE; i++) begin
      if (hit_bus[i]) begin
        binary_way_idx = i[NbLvl-1:0];
      end
    end
  end


  assign ram_addr_o = {binary_way_idx, word};

  assign axi_rdata_o = ram_data_i;

  assign ram_data_o = axi_wdata_i;
  assign ram_we_o = (axi_wready_o && axi_wvalid_i) ? axi_wstrb_i : '0;


  assign plru_access = &tag_valid ? hit_bus : '0;

  plru plru_inst (
      .clk_i(clk_i),
      .rst_ni(rst_ni),
      .access_i(plru_access),
      .lru_way_o(lru_way)
  );




  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      r_state_q <= StRdIdle;
      w_state_q <= StWrIdle;
    end else begin
      r_state_q <= r_state_d;
      w_state_q <= w_state_d;
    end
  end

  always_comb begin

    r_state_d = r_state_q;

    axi_arready_o = 1'b0;
    axi_rvalid_o = 1'b0;

    axi_rresp_o = 2'b00;

    unique case (r_state_q)
      StRdIdle: begin
        if (hit && (state_q == StRead || state_q == StRdWr)) begin
          r_state_d = StRdAddr;
        end
      end

      StRdAddr: begin
        axi_arready_o = 1'b1;

        if (axi_arready_o && axi_arvalid_i) r_state_d = StRdData;
      end

      StRdData: begin
        axi_rvalid_o = 1'b1;

        if (axi_rvalid_o && axi_rready_i) r_state_d = StRdIdle;
      end

      default: ;
    endcase

  end

  always_comb begin

    w_state_d = w_state_q;

    axi_awready_o = 1'b0;
    axi_wready_o = 1'b0;
    axi_bvalid_o = 1'b0;

    axi_bresp_o = 2'b00;

    unique case (w_state_q)
      StWrIdle: begin
        if (hit && state_d == StWrite) begin
          w_state_d = StWrAddr;
          axi_awready_o = 1'b1;
          if (axi_awready_o && axi_awvalid_i) w_state_d = StWrData;
        end
      end

      StWrAddr: begin
        axi_awready_o = 1'b1;

        if (axi_awready_o && axi_awvalid_i) w_state_d = StWrData;
      end

      StWrData: begin
        axi_wready_o = 1'b1;

        if (axi_wready_o && axi_wvalid_i) begin
          axi_bvalid_o = 1'b1;

          if (axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
          else w_state_d = StWrBresp;
        end
      end

      StWrBresp: begin
        axi_bvalid_o = 1'b1;
        if (axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
      end

      default: ;
    endcase

  end

endmodule
