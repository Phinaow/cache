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

  // ------------------------------------------------------------------ //
  // Local parameters
  // ------------------------------------------------------------------ //
  localparam int unsigned NbLvl    = $clog2(NB_LINE);
  localparam int          MemOffset = $clog2(MEM_CACHE_SIZE / NB_LINE);

  // ------------------------------------------------------------------ //
  // Tag / dirty / valid arrays
  // ------------------------------------------------------------------ //
  logic [TAG_SIZE-1:0]  tags     [NB_LINE];
  logic [NB_LINE-1:0]   tag_valid;
  logic [NB_LINE-1:0]   dirty;

  // ------------------------------------------------------------------ //
  // Address breakdown
  // ------------------------------------------------------------------ //
  logic [CPU_ADDR_W-1:0]        addr;
  logic [WORD_SIZE-1:0]         word;
  logic [OFFSET_SIZE-1:0]       offset;   // kept for future misalignment detection
  logic [CPU_ADDR_W-1-TAG_POS:0] overflow; // kept for future SLVERR detection

  // ------------------------------------------------------------------ //
  // Hit detection
  // ------------------------------------------------------------------ //
  logic [NB_LINE-1:0] hit_bus;
  logic               hit;
  assign hit = |hit_bus;

  // ------------------------------------------------------------------ //
  // Line allocation pointer
  // ------------------------------------------------------------------ //
  logic [NbLvl-1:0] line_ptr;   // Sized to index exactly NB_LINE entries

  // ------------------------------------------------------------------ //
  // FSM state types
  // ------------------------------------------------------------------ //
  typedef enum logic [1:0] {
    StIdle  = 2'b00,
    StRead  = 2'b01,
    StWrite = 2'b10,
    StRdWr  = 2'b11
  } access_e;

  typedef enum logic [1:0] {
    StRdIdle = 2'b00,
    StRdAddr = 2'b01,
    StRdData = 2'b10
  } r_state_e;

  typedef enum logic [1:0] {
    StWrIdle  = 2'b00,
    StWrAddr  = 2'b01,
    StWrData  = 2'b10,
    StWrBresp = 2'b11
  } w_state_e;

  access_e  state_q,   state_d;
  r_state_e r_state_q, r_state_d;
  w_state_e w_state_q, w_state_d;

  // ------------------------------------------------------------------ //
  // PLRU
  // ------------------------------------------------------------------ //
  logic [NB_TAG-1:0]  lru_way;
  logic [NB_LINE-1:0] plru_access;

  // Only update PLRU once the cache is full (line_ptr managed allocations before)
  assign plru_access = (&tag_valid) ? hit_bus : '0;

  plru plru_inst (
      .clk_i    (clk_i),
      .rst_ni   (rst_ni),
      .access_i (plru_access),
      .lru_way_o(lru_way)
  );

  // ------------------------------------------------------------------ //
  // chosen_way : allocator pointer when cache not full, LRU otherwise
  // ------------------------------------------------------------------ //
  logic [NB_TAG-1:0] chosen_way;
  assign chosen_way = (!(&tag_valid)) ? NB_TAG'(line_ptr) : lru_way;

  // ------------------------------------------------------------------ //
  // Target state (pure combinational decode of AXI valids)
  // ------------------------------------------------------------------ //
  access_e target_state;

  always_comb begin
    unique case ({axi_arvalid_i, axi_awvalid_i})
      2'b00:   target_state = StIdle;
      2'b10:   target_state = StRead;
      2'b01:   target_state = StWrite;
      2'b11:   target_state = StRdWr;
      default: target_state = StIdle;
    endcase
  end

  // ------------------------------------------------------------------ //
  // Access arbitrator FSM — registered
  // FIX #2: proper else on reset branch
  // ------------------------------------------------------------------ //
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) state_q <= StIdle;
    else         state_q <= state_d;
  end

  // Access arbitrator FSM — combinational next-state
  // Uses state_q only (no dependency on other comb blocks)
  always_comb begin
    state_d = state_q;

    unique case (state_q)
      StIdle: begin
        state_d = target_state;
      end

      StRead: begin
        // Leave read state once the read data handshake is done
        if (r_state_q == StRdData) begin
          state_d = target_state;
        end
      end

      StWrite: begin
        // Leave write state once the write sub-FSM returns to idle
        if (w_state_q == StWrIdle) begin
          state_d = target_state;
        end
      end

      StRdWr: begin
        // Service read first, then move to write
        if (r_state_q == StRdData) begin
          state_d = StWrite;
        end
      end

      default: state_d = StIdle;
    endcase
  end


  // ------------------------------------------------------------------ //
  // Hit detection — uses state_q (stable) instead of state_d
  // FIX #5: avoid inter-comb-block dependency
  // ------------------------------------------------------------------ //
  always_comb begin
    unique case (state_q)
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
        addr    = axi_araddr_i;
        hit_bus = '0;
      end
    endcase
  end

  assign word     = addr[WORD_POS-1:OFFSET_POS];
  assign offset   = addr[OFFSET_POS-1:0];
  assign overflow = addr[CPU_ADDR_W-1:TAG_POS];

  // ------------------------------------------------------------------ //
  // Tag / dirty / valid update — sequential
  // FIX #1: full reset of all arrays and line_ptr
  // FIX #3: line_ptr bounded to NB_LINE-1
  // ------------------------------------------------------------------ //
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      tags      <= '{default: '0};
      tag_valid <= '0;
      dirty     <= '0;
      line_ptr  <= '0;
    end else begin

      if (!hit && state_q != StIdle) begin

        if (!(&tag_valid)) begin
          // ----- Cache not yet full : sequential allocation -----
          if (cdc_ready_i && cdc_valid_o) begin
            tags[line_ptr]      <= addr[TAG_POS-1:WORD_POS];
            tag_valid[line_ptr] <= 1'b1;
            if (state_q == StWrite) dirty[line_ptr] <= 1'b1;

            // FIX #3: guard the increment
            if (line_ptr < NbLvl'(NB_LINE - 1)) begin
              line_ptr <= line_ptr + 1'b1;
            end
          end

        end else begin
          // ----- Cache full : LRU eviction -----
          if (dirty[lru_way]) begin
            // Phase 1 : writeback complete when cdc_ready handshake fires
            // Phase 2 : refill CDC transaction will be started next cycle
            // (cdc_valid_o logic below handles sequencing)
            if (cdc_ready_i && cdc_valid_o) begin
              dirty[lru_way] <= 1'b0;
              // Tag and valid are updated once refill starts (next cdc handshake)
            end
          end else begin
            // No writeback needed : go straight to refill
            if (cdc_ready_i && cdc_valid_o) begin
              tags[lru_way]      <= addr[TAG_POS-1:WORD_POS];
              tag_valid[lru_way] <= 1'b1;
              if (state_q == StWrite) dirty[lru_way] <= 1'b1;
            end
          end
        end

      end else if (hit && state_q != StIdle) begin
        // Hit on a write: mark that line dirty
        if (state_q == StWrite) dirty <= dirty | hit_bus;
      end

    end
  end

  // ------------------------------------------------------------------ //
  // CDC output — combinational
  // Writeback phase : dirty[lru_way] still set  → WRITEBACK transaction
  // Refill   phase : dirty[lru_way] cleared     → REFILL  transaction
  // FIX #7: two-phase sequencing relies on dirty flag being cleared by FF above
  // ------------------------------------------------------------------ //
  always_comb begin
    cdc_valid_o              = 1'b0;
    cdc_data_o.wb_rf         = REFILL;
    cdc_data_o.mem_addr      = {{OVERFLOW{1'b0}}, addr[TAG_POS-1:WORD_POS], {WORD_POS{1'b0}}};
    cdc_data_o.nb_transfer   = 8'((LINE_SIZE * 8) / MEM_DATA_W);
    cdc_data_o.cache_addr    = {chosen_way, {MemOffset{1'b0}}};

    if (!hit && state_q != StIdle) begin

      if (!(&tag_valid)) begin
        // Cache not full → always a refill
        cdc_data_o.wb_rf = REFILL;
        cdc_valid_o      = 1'b1;

      end else begin
        // Cache full — check dirty bit to decide phase
        if (dirty[lru_way]) begin
          // Phase 1: writeback — point mem_addr at evicted line's original address
          cdc_data_o.wb_rf    = WRITEBACK;
          cdc_data_o.mem_addr = {{OVERFLOW{1'b0}}, tags[lru_way], {WORD_POS{1'b0}}};
          cdc_valid_o         = 1'b1;
        end else begin
          // Phase 2 (or clean eviction): refill new line
          cdc_data_o.wb_rf = REFILL;
          cdc_valid_o      = 1'b1;
        end
      end
    end
  end

  // ------------------------------------------------------------------ //
  // RAM address — use chosen_way on a miss so address stays valid
  // FIX #8: avoid binary_way_idx=0 default on miss
  // ------------------------------------------------------------------ //
  logic [NbLvl-1:0] binary_way_idx;

  always_comb begin
    binary_way_idx = '0;
    for (int i = 0; i < NB_LINE; i++) begin
      if (hit_bus[i]) binary_way_idx = NbLvl'(i);
    end
  end

  // On a hit  → use the matched way
  // On a miss → point at chosen_way so any fill write lands in the right place
  assign ram_addr_o = hit ? {binary_way_idx, word} : {chosen_way[NbLvl-1:0], word};

  assign axi_rdata_o = ram_data_i;
  assign ram_data_o  = axi_wdata_i;
  assign ram_we_o    = (axi_wready_o && axi_wvalid_i) ? axi_wstrb_i : '0;

  // ------------------------------------------------------------------ //
  // AXI Read sub-FSM
  // ------------------------------------------------------------------ //
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) r_state_q <= StRdIdle;
    else         r_state_q <= r_state_d;
  end

  always_comb begin
    r_state_d    = r_state_q;
    axi_arready_o = 1'b0;
    axi_rvalid_o  = 1'b0;
    axi_rresp_o   = 2'b00;

    // FIX: misalignment / overflow error reporting (previously unused signals)
    if (offset != '0)   axi_rresp_o = 2'b10; // SLVERR on misaligned access
    if (overflow != '0) axi_rresp_o = 2'b10; // SLVERR on out-of-range access

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

      default: r_state_d = StRdIdle;
    endcase
  end

  // ------------------------------------------------------------------ //
  // AXI Write sub-FSM
  // FIX #4: removed self-defeating combinational awready check in StWrIdle
  // ------------------------------------------------------------------ //
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) w_state_q <= StWrIdle;
    else         w_state_q <= w_state_d;
  end

  always_comb begin
    w_state_d    = w_state_q;
    axi_awready_o = 1'b0;
    axi_wready_o  = 1'b0;
    axi_bvalid_o  = 1'b0;
    axi_bresp_o   = 2'b00;

    unique case (w_state_q)
      StWrIdle: begin
        // FIX #4: transition registered — awready combinationally asserted
        // only while in StWrAddr, not from StWrIdle, to avoid the self-check bug.
        // Detect hit on write and move to StWrAddr unconditionally.
        if (hit && state_q == StWrite) begin
          w_state_d = StWrAddr;
        end
      end

      StWrAddr: begin
        axi_awready_o = 1'b1;
        // The master sees awready high this cycle; latch and move to data phase
        if (axi_awready_o && axi_awvalid_i) w_state_d = StWrData;
      end

      StWrData: begin
        axi_wready_o = 1'b1;
        if (axi_wready_o && axi_wvalid_i) begin
          axi_bvalid_o = 1'b1;
          if (axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
          else                               w_state_d = StWrBresp;
        end
      end

      StWrBresp: begin
        axi_bvalid_o = 1'b1;
        if (axi_bvalid_o && axi_bready_i) w_state_d = StWrIdle;
      end

      default: w_state_d = StWrIdle;
    endcase
  end


endmodule
