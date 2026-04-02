from verible_struct_parser import *

result={'parameters': {'MEM_ADDR_W': 32, 'MEM_DATA_W': 128, 'MEM_SIZE': 536870912, 'CPU_DATA_W': 32, 'CPU_ADDR_W': 32, 'CPU_CACHE_SIZE': 512, 'MEM_CACHE_SIZE': 128, 'CPU_CACHE_ADDR_W': 9, 'MEM_CACHE_ADDR_W': 7, 'CACHE_SIZE': 2048, 'NB_LINE': 4, 'NB_TAG': 2, 'LINE_SIZE': 512, 'OFFSET_SIZE': 2, 'WORD_SIZE': 7, 'TAG_SIZE': 20, 'OFFSET_POS': 2, 'WORD_POS': 9, 'TAG_POS': 29, 'OVERFLOW': 3}, 'structs': {'cache_op_t': StructDef(name='cache_op_t', members=[
    LogicMember(name='mem_addr', msb=31, lsb=0),
    LogicMember(name='nb_transfer', msb=7, lsb=0),
    LogicMember(name='cache_addr', msb=6, lsb=0),
]), 'cdc_data_t': StructDef(name='cdc_data_t', members=[
    LogicMember(name='mem_addr', msb=31, lsb=0),
    LogicMember(name='nb_transfer', msb=7, lsb=0),
    LogicMember(name='cache_addr', msb=6, lsb=0),
    EnumMember(name='wb_rf', type_name='rf_wb_e', size=1),
])}, 'enums': {'rf_wb_e': EnumDef(name='rf_wb_e', size=1, values={'REFILL': 0, 'WRITEBACK': 1})}, 'modules': {}}
MEM_ADDR_W = 32
MEM_DATA_W = 128
MEM_SIZE = 536870912
CPU_DATA_W = 32
CPU_ADDR_W = 32
CPU_CACHE_SIZE = 512
MEM_CACHE_SIZE = 128
CPU_CACHE_ADDR_W = 9
MEM_CACHE_ADDR_W = 7
CACHE_SIZE = 2048
NB_LINE = 4
NB_TAG = 2
LINE_SIZE = 512
OFFSET_SIZE = 2
WORD_SIZE = 7
TAG_SIZE = 20
OFFSET_POS = 2
WORD_POS = 9
TAG_POS = 29
OVERFLOW = 3
REFILL = 0
WRITEBACK = 1
