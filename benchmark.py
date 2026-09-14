#!/usr/bin/env python3
"""CPU-bound threaded benchmark. Stdlib only — no wheels, no GIL surprises.

Compare the same workload on a GIL-enabled 3.14 interpreter and a
free-threaded 3.14t one:

    uv run --no-project --isolated --python 3.14+gil python benchmark.py
    uv run --no-project --isolated --python 3.14t python benchmark.py
"""

from __future__ import annotations

import argparse
import os
import sys
import sysconfig
import time
from concurrent.futures import ThreadPoolExecutor


def crunch(n: int) -> int:
    """Pure-Python CPU work: parse a CSV-ish row and fold the fields.

    Stays in bytecode on purpose. hashlib and NumPy can release the GIL
    internally, which would fake a speedup on the default build.
    """
    acc = 0
    for i in range(n):
        a, b, c = f"{i},{i * i},{i % 97}".split(",")
        acc += int(a) + int(b) + int(c)
        acc ^= acc << 1
        acc &= 0xFFFFFFFF
    return acc


def wall_time(workers: int, total: int) -> float:
    chunk, rem = divmod(total, workers)
    sizes = [chunk + (1 if i < rem else 0) for i in range(workers)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(crunch, sizes))
    return time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser(description="Threaded CPU benchmark")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--n", type=int, default=2_000_000)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()

    gil = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else "n/a"
    print(f"Python          {sys.version.splitlines()[0]}")
    print(f"Py_GIL_DISABLED {sysconfig.get_config_var('Py_GIL_DISABLED')}")
    print(f"GIL enabled     {gil}")
    print(f"CPU count       {os.cpu_count()}")
    print(f"total rows      {args.n:,}  (split across threads)")
    print()
    print(f"{'threads':>8}  {'wall s':>10}  {'speedup':>8}")

    baseline = None
    for workers in (1, args.workers):
        best = min(wall_time(workers, args.n) for _ in range(args.repeat))
        if baseline is None:
            baseline = best
        print(f"{workers:>8}  {best:>10.3f}  {baseline / best:>7.2f}x")


if __name__ == "__main__":
    main()
