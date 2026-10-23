# Run from the repository root with Vivado 2025.2 in batch mode.
# Build artifacts stay under sim_build; no generated IP source is hand-edited.
set root [file normalize [file join [file dirname [info script]] ..]]
set build [file join $root sim_build vivado ram_ip]
create_project -force ram_ip $build -part xc7a200tsbg484-1
create_ip -name blk_mem_gen -vendor xilinx.com -library ip -version 8.4 -module_name cache_ram_ip
set_property -dict [list \
  CONFIG.Memory_Type {True_Dual_Port_RAM} \
  CONFIG.Byte_Size {8} \
  CONFIG.Use_Byte_Write_Enable {true} \
  CONFIG.Write_Width_A {128} \
  CONFIG.Write_Depth_A {512} \
  CONFIG.Read_Width_A {128} \
  CONFIG.Write_Width_B {32} \
  CONFIG.Read_Width_B {32} \
  CONFIG.Operating_Mode_A {READ_FIRST} \
  CONFIG.Operating_Mode_B {READ_FIRST} \
  CONFIG.Enable_A {Use_ENA_Pin} \
  CONFIG.Enable_B {Use_ENB_Pin} \
  CONFIG.Register_PortA_Output_of_Memory_Primitives {false} \
  CONFIG.Register_PortB_Output_of_Memory_Primitives {false} \
  CONFIG.Register_PortA_Output_of_Memory_Core {false} \
  CONFIG.Register_PortB_Output_of_Memory_Core {false} \
] [get_ips cache_ram_ip]
generate_target all [get_ips cache_ram_ip]
export_ip_user_files -of_objects [get_ips cache_ram_ip] -no_script -sync -force
close_project
