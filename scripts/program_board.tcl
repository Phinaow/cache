# Volatile configuration only: no flash writes. Require one matching FPGA.
set bitstream [file normalize [lindex $argv 0]]
if {![file exists $bitstream]} { error "Bitstream not found: $bitstream" }
open_hw_manager
connect_hw_server -allow_non_jtag
set targets {}
foreach target [get_hw_targets] {
  if {[string match *210276B063C4* $target]} { lappend targets $target }
}
if {[llength $targets] != 1} { error "Expected the connected Nexys Video target" }
current_hw_target [lindex $targets 0]
open_hw_target
set devices [get_hw_devices xc7a200t*]
if {[llength $devices] != 1} { error "Expected one xc7a200t FPGA" }
set device [lindex $devices 0]
current_hw_device $device
set_property PROGRAM.FILE $bitstream $device
program_hw_devices $device
refresh_hw_device $device
puts "CACHE_FPGA_PROGRAMMED $bitstream"
close_hw_target
disconnect_hw_server
close_hw_manager
