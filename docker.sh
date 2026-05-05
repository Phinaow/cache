#!/bin/bash

docker volume create vscode_extensions_cache

BUILD=0
ROOT=0
IMAGE="my_cocotb_env"

while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD=1
            shift
            ;;
        --root)
            ROOT=1
            shift
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

if [[ $BUILD -eq 1 ]]; then
    docker build --build-arg JOBS=$(nproc) -t $IMAGE .
fi

USER_FLAGS=""
VSCODE_MOUNT="/root/.vscode-server"

# if [[ $ROOT -eq 1 ]]; then
#     VSCODE_MOUNT="/root/.vscode-server"
# else
#     USER_FLAGS="--user $(id -u):$(id -g) -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro"
#     VSCODE_MOUNT="/work/.vscode-server"
# fi

docker run $USER_FLAGS -d --name cache_design -it --rm \
    --entrypoint /bin/bash \
    -v vscode_extensions_cache:$VSCODE_MOUNT \
    -v "${PWD}:/work" \
    -w /work \
    $IMAGE