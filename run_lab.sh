#!/usr/bin/env bash
set -euo pipefail

# Compare GIL-on 3.14 against free-threaded 3.14t, then prove a
# non-ready C extension can put the GIL back on.
export PATH="${HOME}/.local/bin:${PATH}"

uv python install 3.14 3.14t

echo "===== 3.14 (GIL on) ====="
uv run --no-project --isolated --python 3.14+gil python benchmark.py

echo
echo "===== 3.14t (free-threaded) ====="
uv run --no-project --isolated --python 3.14t python benchmark.py

echo
echo "===== GIL detector: stdlib ====="
uv run --no-project --isolated --python 3.14t python gil_detector.py json hashlib threading

echo
echo "===== GIL detector: unmarked C extension ====="
uv run --no-project --isolated --python 3.14t --with ./trap python gil_detector.py gil_trap
