# Compare RTL against the actual generated Block Memory Generator model in XSim.
set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root sim_build vivado ram_ip ram_ip.xpr]
add_files -norecurse [list \
  [file join $root src cache_pkg.sv] \
  [file join $root src bl_mem.sv] \
  [file join $root src true_dual_port_ram.sv]]
add_files -fileset sim_1 -norecurse [file join $root test rtl ram_backend_tb.sv]
set_property top ram_backend_tb [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sim_1
launch_simulation
close_sim
set logfile [file join $root sim_build vivado ram_ip ram_ip.sim sim_1 behav xsim simulate.log]
set handle [open $logfile r]
set transcript [read $handle]
close $handle
if {[string first "RAM_BACKEND_EQUIVALENCE_PASSED" $transcript] < 0 ||
    [string first "Fatal:" $transcript] >= 0} {
  error "RAM backend equivalence failed; inspect $logfile"
}
close_project
