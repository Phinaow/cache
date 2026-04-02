#!/bin/bash

docker volume create vscode_extensions_cache

docker build . -t my_cocotb_env

docker run -d --name cache_design -it --rm \
    --entrypoint /bin/bash \
    -v vscode_extensions_cache:/root/.vscode-server \
    -v ${PWD}:/work \
    -w /work \
    my_cocotb_env