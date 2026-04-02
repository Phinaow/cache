module true_dual_port_ram import cache_pkg::*;
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

endmodule
