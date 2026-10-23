module true_dual_port_ram import cache_pkg::*;
#(parameter bit USE_VENDOR_RAM = 1'b0)
(
    input logic clka,
    input logic ena,
    input logic [(MEM_DATA_W/8)-1:0] wea,
    input logic [MEM_CACHE_ADDR_W-1:0] addra,
    input logic [MEM_DATA_W-1:0] dina,
    output logic [MEM_DATA_W-1:0] douta,

    input logic clkb,
    input logic enb,
    input logic [(CPU_DATA_W/8)-1:0] web,
    input logic [CPU_CACHE_ADDR_W-1:0] addrb,
    input logic [CPU_DATA_W-1:0] dinb,
    output logic [CPU_DATA_W-1:0] doutb
);

  if (USE_VENDOR_RAM) begin : vendor
    cache_ram_ip memory (
      .clka(clka), .ena(ena), .wea(wea), .addra(addra), .dina(dina), .douta(douta),
      .clkb(clkb), .enb(enb), .web(web), .addrb(addrb), .dinb(dinb), .doutb(doutb)
    );
  end else begin : rtl
    bl_mem #(
      .PORTA_BYTES(CPU_DATA_W / 8), .PORTB_BYTES(MEM_DATA_W / 8),
      .PORTA_DEPTH(CPU_CACHE_SIZE)
    ) memory (
      .clk_a(clkb), .en_a(enb), .strb_a(web), .addr_a(addrb), .wdata_a(dinb), .rdata_a(doutb),
      .clk_b(clka), .en_b(ena), .strb_b(wea), .addr_b(addra), .wdata_b(dina), .rdata_b(douta)
    );
  end
endmodule
