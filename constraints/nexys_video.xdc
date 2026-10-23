# Nexys Video Rev. A pins, checked against Digilent's master XDC and manual:
# https://github.com/Digilent/digilent-xdc/blob/master/Nexys-Video-Master.xdc
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property -dict {PACKAGE_PIN R4 IOSTANDARD LVCMOS33} [get_ports sys_clk_i]
# The clock-wizard in-context XDC defines the 100 MHz input clock.
set_property -dict {PACKAGE_PIN AA19 IOSTANDARD LVCMOS33} [get_ports tx]
set_property -dict {PACKAGE_PIN V18 IOSTANDARD LVCMOS33} [get_ports rx]
set_property -dict {PACKAGE_PIN G4 IOSTANDARD LVCMOS15} [get_ports sys_rst]
set_property -dict {PACKAGE_PIN T14 IOSTANDARD LVCMOS25} [get_ports {led[0]}]
set_property -dict {PACKAGE_PIN T15 IOSTANDARD LVCMOS25} [get_ports {led[1]}]
set_property -dict {PACKAGE_PIN T16 IOSTANDARD LVCMOS25} [get_ports {led[2]}]
set_property -dict {PACKAGE_PIN U16 IOSTANDARD LVCMOS25} [get_ports {led[3]}]
set_property -dict {PACKAGE_PIN V15 IOSTANDARD LVCMOS25} [get_ports {led[4]}]
set_property -dict {PACKAGE_PIN W16 IOSTANDARD LVCMOS25} [get_ports {led[5]}]
set_property -dict {PACKAGE_PIN W15 IOSTANDARD LVCMOS25} [get_ports {led[6]}]
set_property -dict {PACKAGE_PIN Y13 IOSTANDARD LVCMOS25} [get_ports {led[7]}]
# These external signals have no synchronous relationship to the board clock.
set_false_path -from [get_ports sys_rst]
set_false_path -to [get_ports {tx led[*]}]
set_false_path -from [get_ports rx]
