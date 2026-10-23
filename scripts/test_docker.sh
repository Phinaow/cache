#!/usr/bin/env bash
# Run the regression in the existing container without rebuilding the image.
set -euo pipefail
if [[ $# -eq 0 ]]; then
    set -- -q test
fi
docker exec -w /phinaow cache_design bash -lc '
    ulimit -c 0
    python_path=/opt/cache-venv/bin/python
    if [[ ! -x "$python_path" ]]; then
        python_path=/tmp/cache-cocotb-venv/bin/python
    fi
    export PYTHONPATH=/phinaow:/phinaow/test
    export LIBPYTHON_LOC=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
    exec "$python_path" -m pytest "$@"
' cache-tests "$@"
