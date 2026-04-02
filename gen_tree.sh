#!/bin/bash

verible-verilog-syntax --export_json --printtree "$@" > "tree.json"
