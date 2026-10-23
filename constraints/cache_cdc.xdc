# Cut only the first synchronizer stage, not either complete clock domain.
set first_stages [get_cells -quiet -hier -regexp {.*(request_sync_q_reg|acknowledge_sync_q_reg)\[0\]}]
set_false_path -to [get_pins -of_objects $first_stages -filter {REF_PIN_NAME == D}]
# Bound each bundled-data mailbox bus below the request synchronization gap.
# Explicit paths keep this file within the subset of Tcl supported by XDC.
set request_source [get_cells -quiet -hier -filter {NAME =~ */controller_req/source_data_q_reg*}]
set request_destination [get_cells -quiet -hier -filter {NAME =~ */controller_req/dst_data_o_reg*}]
set_max_delay -datapath_only 10.000 -from $request_source -to $request_destination
set_bus_skew 10.000 -from $request_source -to $request_destination
set response_source [get_cells -quiet -hier -filter {NAME =~ */miss_handler_resp/source_data_q_reg*}]
set response_destination [get_cells -quiet -hier -filter {NAME =~ */miss_handler_resp/dst_data_o_reg*}]
set_max_delay -datapath_only 10.000 -from $response_source -to $response_destination
set_bus_skew 10.000 -from $response_source -to $response_destination
