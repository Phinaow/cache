// Vendor-model equivalence test. Run with scripts/simulate_ram_backends.tcl.
module ram_backend_tb;
  timeunit 1ns;
  timeprecision 1ps;
  logic clka = 0, clkb = 0;
  logic ena = 0, enb = 0;
  logic [15:0] wea = 0;
  logic [3:0] web = 0;
  logic [8:0] addra = 0;
  logic [10:0] addrb = 0;
  logic [127:0] dina = 0, rtl_a, vendor_a;
  logic [31:0] dinb = 0, rtl_b, vendor_b;
  logic [31:0] expected [2048];

  true_dual_port_ram #(.USE_VENDOR_RAM(0)) rtl (
    .clka, .ena, .wea, .addra, .dina, .douta(rtl_a),
    .clkb, .enb, .web, .addrb, .dinb, .doutb(rtl_b)
  );
  true_dual_port_ram #(.USE_VENDOR_RAM(1)) vendor (
    .clka, .ena, .wea, .addra, .dina, .douta(vendor_a),
    .clkb, .enb, .web, .addrb, .dinb, .doutb(vendor_b)
  );

  task automatic cpu_edge;
    #3; clkb = 1; #1;
  endtask
  task automatic memory_edge;
    #5; clka = 1; #1;
  endtask

  initial begin
    // Initialize all bytes before checking any value returned by either RAM.
    enb = 1;
    web = '1;
    for (int word = 0; word < 2048; word++) begin
      addrb = 11'(word);
      expected[word] = $urandom;
      dinb = expected[word];
      cpu_edge();
      #2; clkb = 0;
    end
    enb = 0;
    web = 0;
    ena = 1;
    for (int word = 0; word < 512; word++) begin
      addra = 9'(word);
      memory_edge();
      if (rtl_a !== vendor_a) $fatal(1, "Wide-port backend mismatch at %0d: RTL=%032h IP=%032h expected=%032h", word, rtl_a, vendor_a, {expected[word*4+3], expected[word*4+2], expected[word*4+1], expected[word*4]});
      for (int lane = 0; lane < 4; lane++) begin
        if (rtl_a[lane*32 +: 32] !== expected[word*4 + lane])
          $fatal(1, "Incorrect wide-port mapping");
      end
      #4; clka = 0;
    end
    ena = 0;
    enb = 1;
    // All narrow masks, all RAM addresses, READ_FIRST and preserved bytes.
    for (int word = 0; word < 2048; word++) begin
      addrb = 11'(word);
      dinb = $urandom;
      web = 4'(word % 16);
      cpu_edge();
      if (rtl_b !== vendor_b || rtl_b !== expected[word])
        $fatal(1, "Narrow READ_FIRST mismatch at %0d", word);
      for (int byte_index = 0; byte_index < 4; byte_index++) begin
        if (web[byte_index]) expected[word][byte_index*8 +: 8] = dinb[byte_index*8 +: 8];
      end
      #2; clkb = 0;
    end
    enb = 0;
    web = 0;
    ena = 1;
    for (int word = 0; word < 512; word++) begin
      addra = 9'(word);
      dina = {$urandom, $urandom, $urandom, $urandom};
      wea = 16'(word * 131);
      memory_edge();
      if (rtl_a !== vendor_a) $fatal(1, "Wide READ_FIRST mismatch at %0d", word);
      for (int lane = 0; lane < 4; lane++) begin
        if (rtl_a[lane*32 +: 32] !== expected[word*4 + lane])
          $fatal(1, "Lost narrow masked write");
      end
      for (int byte_index = 0; byte_index < 16; byte_index++) begin
        if (wea[byte_index])
          expected[word*4 + byte_index/4][(byte_index%4)*8 +: 8] = dina[byte_index*8 +: 8];
      end
      #4; clka = 0;
    end
    ena = 0;
    wea = 0;
    enb = 1;
    for (int word = 0; word < 2048; word++) begin
      addrb = 11'(word);
      cpu_edge();
      if (rtl_b !== vendor_b || rtl_b !== expected[word])
        $fatal(1, "Lost wide masked write at %0d", word);
      #2; clkb = 0;
    end
    $display("RAM_BACKEND_EQUIVALENCE_PASSED");
    $finish;
  end
  initial begin
    #100000;
    $fatal(1, "RAM equivalence timeout");
  end
endmodule
