# Isolated proof that the RTL backend maps to Artix-7 block RAM.
set root [file normalize [file join [file dirname [info script]] ..]]
set output [file join $root sim_build vivado]
file mkdir $output
read_verilog -sv [file join $root src bl_mem.sv]
synth_design -top bl_mem -part xc7a200tsbg484-1
set blocks [get_cells -hier -filter {REF_NAME =~ RAMB*}]
if {[llength $blocks] == 0} { error "RTL RAM did not infer any block RAM" }
report_utilization -file [file join $output ram_utilization.rpt]
write_checkpoint -force [file join $output ram.dcp]
