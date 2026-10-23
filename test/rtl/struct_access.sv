// Isolated VPI capability check: input fields, output fields and packed layout.
module struct_access import cache_pkg::*; (
    input cdc_data_t command_i,
    output cdc_data_t command_o,
    output logic [MEM_ADDR_W-1:0] address_o,
    output logic [$bits(cdc_data_t)-1:0] packed_o
);
  assign command_o = command_i;
  assign address_o = command_i.mem_addr;
  assign packed_o = command_i;
endmodule
