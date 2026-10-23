# Continue an existing build after RTL/constraint corrections without regenerating IP.
set root [file normalize [file join [file dirname [info script]] ..]]
set backend [lindex $argv 0]
if {$backend eq ""} { set backend ip }
set output [file join $root sim_build vivado fpga_$backend]
open_project [file join $output cache_fpga.xpr]
update_compile_order -fileset sources_1
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Synthesis failed" }
open_run synth_1
report_cdc -details -file [file join $output cdc.rpt]
report_utilization -file [file join $output utilization.rpt]
report_drc -file [file join $output drc.rpt]
check_timing -verbose -file [file join $output check_timing.rpt]
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
