module cache_controller
  import cache_pkg::*;
(
    input  logic                        clk_i,
    input  logic                        rst_ni,

    input  logic [      CPU_ADDR_W-1:0] cpu_addr_i,
    input  logic [      CPU_DATA_W-1:0] cpu_din_i,
    input  logic                        cpu_req_i,
    input  logic                        cpu_we_i,
    output logic [      CPU_DATA_W-1:0] cpu_dout_o,
    input  logic                        cpu_valid,
    output logic                        cpu_ready_o,

    output logic [CPU_CACHE_ADDR_W-1:0] ram_addr_a_o,
    output logic [      CPU_DATA_W-1:0] ram_din_a_o,
    input  logic [      CPU_DATA_W-1:0] ram_dout_a_i,
    output logic                        ram_we_a_o,

    output logic                        start_refill_o,
    output logic                        start_wb_o,
    output logic [      MEM_ADDR_W-1:0] target_addr_o,
    input  logic                        mig_done_i
);

  typedef enum {
    StIdle,
    StCompare,
    StWriteback,
    StRefill,
    StWaitMIG,
    StAccess
  } state_e;

  state_e state;

  // Registres de la ligne de cache
  logic   [CPU_ADDR_W-1:11] tag_reg;
  logic                     valid_bit;
  logic                     dirty_bit;

  // Extraction des champs de l'adresse
  logic   [           20:0] addr_tag;
  logic   [            8:0] addr_index;
  logic   [            1:0] addr_offset;

  assign addr_tag    = cpu_addr_i[31:11];
  assign addr_index  = cpu_addr_i[10:2];
  assign addr_offset = cpu_addr_i[1:0];

  logic hit;
  assign hit = valid_bit && (tag_reg == addr_tag);

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state                        <= StIdle;
      valid_bit                    <= 1'b0;
      dirty_bit                    <= 1'b0;
      cpu_ready_o                  <= 1'b0;
      {start_refill_o, start_wb_o} <= 2'b00;
    end else begin
      unique case (state)
        StIdle: begin
          cpu_ready_o <= 1'b0;
          if (cpu_req_i) state <= StCompare;
        end

        StCompare: begin
          if (hit) begin
            state <= StAccess;
          end else begin

            target_addr_o <= {tag_reg, 11'h0};
            if (valid_bit && dirty_bit) begin
              start_wb_o <= 1'b1;
              state      <= StWriteback;
            end else begin
              start_refill_o <= 1'b1;
              target_addr_o  <= {addr_tag, 11'h0};
              state          <= StRefill;
            end
          end
        end

        StWriteback: begin
          start_wb_o <= 1'b0;
          if (mig_done_i) begin
            start_refill_o <= 1'b1;
            target_addr_o  <= {addr_tag, 11'h0};
            state          <= StRefill;
          end
        end

        StRefill: begin
          start_refill_o <= 1'b0;
          if (mig_done_i) begin
            tag_reg   <= addr_tag;
            valid_bit <= 1'b1;
            dirty_bit <= 1'b0;
            state     <= StAccess;
          end
        end

        StAccess: begin
          if (cpu_we_i) dirty_bit <= 1'b1;
          cpu_ready_o <= 1'b1;

          if (cpu_valid) state <= StIdle;
        end

        default:;
      endcase
    end
  end

  assign ram_addr_a_o = addr_index;

  assign ram_din_a_o  = cpu_din_i;
  assign ram_we_a_o   = cpu_we_i;

  assign cpu_dout_o   = ram_dout_a_i;

endmodule
