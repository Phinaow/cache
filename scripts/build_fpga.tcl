# Usage: vivado -mode batch -source scripts/build_fpga.tcl -tclargs ip|rtl [impl]
set root [file normalize [file join [file dirname [info script]] ..]]
set backend [lindex $argv 0]
if {$backend eq ""} { set backend ip }
if {$backend ni {ip rtl}} { error "RAM backend must be ip or rtl" }
set use_vendor [expr {$backend eq "ip"}]
set output [file join $root sim_build vivado fpga_$backend]
set ram_xci [file join $root sim_build vivado ram_ip ram_ip.srcs sources_1 ip cache_ram_ip cache_ram_ip.xci]
if {$use_vendor && ![file exists $ram_xci]} { source [file join $root scripts create_ram_ip.tcl] }
create_project -force cache_fpga $output -part xc7a200tsbg484-1
set_property target_language Verilog [current_project]
if {$use_vendor} { read_ip $ram_xci }

create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 -module_name clk_ref_mig
set_property -dict [list \
  CONFIG.PRIM_IN_FREQ {100.000} \
  CONFIG.PRIMARY_PORT {clk} \
  CONFIG.CLK_OUT1_PORT {clk_ref} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {200.000} \
  CONFIG.CLK_OUT2_PORT {clk_cpu} CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {50.000} CONFIG.CLKOUT2_USED {true} \
  CONFIG.CLK_OUT3_PORT {clk_mig} CONFIG.CLKOUT3_REQUESTED_OUT_FREQ {100.000} CONFIG.CLKOUT3_USED {true} \
  CONFIG.NUM_OUT_CLKS {3}] [get_ips clk_ref_mig]

# The MIG system clock is driven by the clock wizard, not by a second board pin.
set handle [open [file join $root vivado mig.prj] r]
set xml [read $handle]
close $handle
set xml [string map {<SystemClock>Single-Ended</SystemClock> <SystemClock>No\ Buffer</SystemClock>} $xml]
set mig_configuration [file join $output mig_internal_clock.prj]
set handle [open $mig_configuration w]
puts -nonewline $handle $xml
close $handle
create_ip -name mig_7series -vendor xilinx.com -library ip -module_name adam_mig
set_property CONFIG.XML_INPUT_FILE $mig_configuration [get_ips adam_mig]
generate_target all [get_ips]

set handle [open [file join $root src cache.f] r]
foreach source [split [read $handle] \n] {
  if {$source ne ""} { add_files -norecurse [file join $root $source] }
}
close $handle
add_files -norecurse [file join $root src top_cache.sv]
foreach name {uart_rx uart_tx r_buffer t_buffer data_to_axi uart_to_axi uart_to_cache} {
  add_files -norecurse [file join $root src uart $name.sv]
}
set_property top uart_to_cache [get_filesets sources_1]
set_property generic USE_VENDOR_RAM=$use_vendor [get_filesets sources_1]
add_files -fileset constrs_1 -norecurse [file join $root constraints nexys_video.xdc]
add_files -fileset constrs_1 -norecurse [file join $root constraints cache_cdc.xdc]
set_property PROCESSING_ORDER LATE [get_files cache_cdc.xdc]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Synthesis failed" }
open_run synth_1
report_utilization -file [file join $output utilization.rpt]
report_cdc -details -file [file join $output cdc.rpt]
check_timing -verbose -file [file join $output check_timing.rpt]
report_drc -file [file join $output drc.rpt]
if {[lindex $argv 1] eq "impl"} {
  launch_runs impl_1 -to_step write_bitstream -jobs 4
  wait_on_run impl_1
  if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "Implementation failed" }
  open_run impl_1
  report_timing_summary -report_unconstrained -file [file join $output timing.rpt]
  report_bus_skew -file [file join $output bus_skew.rpt]
  report_cdc -details -file [file join $output cdc_routed.rpt]
  report_drc -file [file join $output drc_routed.rpt]
}
close_project
