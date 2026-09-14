# The GIL Is Optional. Your Dependencies Aren’t.

Python 3.14 made the free-threaded build officially supported. That is the changelog line. The part that will waste an afternoon is quieter: you can be on `3.14t`, see `free-threading build` in `python -VV`, and still be running with the GIL on because a C extension you imported was not ready.

Threads did not fail. They went back to taking turns. Unless you asked `sys._is_gil_enabled()`, you would not know.

> ONE THING: Free-threading is a build plus an ecosystem decision, not a one-line upgrade.

## Why this matters now

For twenty years the rule was simple. The global interpreter lock lets only one thread execute Python bytecode at a time. Threads were fine for waiting on sockets. They did nothing for CPU-bound Python. You wanted cores, you paid for processes.

Python 3.13 shipped an experimental free-threaded build. Python 3.14, via [PEP 779](https://peps.python.org/pep-0779/), moved it to officially supported. It is still optional. Default `python3.14` still has the GIL. Phase III — free-threading as the default — is not this release, and the Steering Council has not scheduled it.

So the interesting question is not "did they remove the GIL?" They did not, not on the interpreter most people will install. The interesting question is: if you install the other build, what actually gets faster, and what silently puts the lock back?

This lab answers that with uv, a stdlib-only benchmark, and one unmarked C extension.

## What "free-threaded" actually means

It is a separate interpreter, not a flag you flip on normal 3.14. The binary is `python3.14t`. uv spells the request `3.14t` or `3.14+freethreaded`. Wheel tags pick up a `t`: `cp314t` versus `cp314`. Those ABIs are not interchangeable.

On that build, Python threads can run bytecode in parallel on multiple cores. The cost is a single-thread tax. CPython cites roughly 5–10% depending on platform and compiler. On the pyperformance suite the overhead has landed closer to 1% on macOS aarch64 and 8% on x86-64 Linux. Treat those as order of magnitude, not a number to put in a budget slide.

Check you are on it:

```bash
python -VV
# Python 3.14.7 free-threading build ...
```

```python
import sys
import sysconfig

sysconfig.get_config_var("Py_GIL_DISABLED")  # 1 on a free-threaded build
sys._is_gil_enabled()                        # False — until something flips it
```

`Py_GIL_DISABLED` is the compile-time fact. `sys._is_gil_enabled()` is the runtime fact. You need both. The build can support free-threading and still be running with the GIL on.

You can also force the lock from the command line (`-X gil=1`) or the environment (`PYTHON_GIL=1`). That is the honest switch. The dishonest one is an import.

## Lab setup

Pin the interpreter in the project so CI cannot "helpfully" pick default 3.14.

```bash
uv python install 3.14 3.14t
uv python pin 3.14t          # writes .python-version
```

Keep `requires-python = ">=3.14"` in `pyproject.toml`. The `t` suffix is a build variant, not a language version. uv will refuse `>=3.14t`.

When you want the GIL build back for a comparison, ask for it by name. A `.python-version` of `3.14t` plus an existing `.venv` will swallow a vague `--python 3.14`.

```bash
uv run --no-project --isolated --python 3.14+gil python benchmark.py
uv run --no-project --isolated --python 3.14t python benchmark.py
```

Keep the first benchmark stdlib-only. The moment you import a wheel, you are no longer measuring threads. You are measuring whether that wheel opted in.

## The benchmark

Same total work, split across 1 thread then N threads. Pure Python on purpose: format a row, split it, fold integers. `hashlib` and NumPy can release the GIL from C, which would fake a win on the default build.

```python
from concurrent.futures import ThreadPoolExecutor
import time

def crunch(n: int) -> int:
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
```

The full script in this repo prints interpreter metadata, repeats the run, and keeps the best wall time.

### What I measured

Hardware: 4 vCPU Intel Xeon (KVM guest), Linux x86_64, CPython 3.14.7, uv 0.12.13. Workload: 2,000,000 rows, best of 3.

| Build | GIL | 1 thread | 4 threads | Speedup |
| --- | --- | --- | --- | --- |
| 3.14 (`3.14+gil`) | on | 1.024 s | 1.023 s | 1.00× |
| 3.14t | off | 1.053 s | 0.262 s | 4.01× |

Default 3.14: four threads, same wall clock as one. That is the punchline you already knew.

3.14t: 4.01× on four cores. That is the other punchline, and you should not trust it yet.

This job shares nothing. No mutable dict, no pandas frame, no lock. Linear scaling is the lab ceiling, not a promise. Contention, allocator traffic, and native code that still serializes will pull you toward 2×. 4× on four cores is rare in production. Treat 2× as a win. If you see 1.1×, you are paying the single-thread tax for nothing.

The tax showed up here too: 1.053 / 1.024, about 3% slower on one thread. CPython's 5–10% band is the number to remember. On a single-threaded CLI that 5–10% is pure cost.

## The gotcha that kills the story

Import a C-API extension that has not declared it can run without the GIL, and the interpreter turns the lock back on for the rest of the process. It prints a warning. It does not raise. Your benchmark keeps running. Your threads keep looking busy. Throughput goes back to 2012.

The detector is a loop, not a framework:

```python
import importlib, sys, warnings

print("before", sys._is_gil_enabled())  # False on a fresh 3.14t

for name in ["numpy", "pandas", "gil_trap"]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module(name)
        print(name, sys._is_gil_enabled())
        for w in caught:
            if "gil" in str(w.message).lower():
                print(" ", w.message)
```

Start free-threaded. Import dependencies one by one. Watch for the flip.

This repo ships `trap/`: a C extension that does no work and does not set `Py_MOD_GIL_NOT_USED`. That is enough.

```bash
uv run --no-project --isolated --python 3.14t --with ./trap python gil_detector.py gil_trap
```

```
before imports               gil_enabled=False
gil_trap                     gil_enabled=True  <-- GIL re-enabled
                             warning: The global interpreter lock (GIL) has been
                             enabled to load module 'gil_trap', which has not
                             declared that it can run safely without the GIL.
                             To override this behavior and keep the GIL disabled
                             (at your own risk), run with PYTHON_GIL=0 or -Xgil=0.
```

`PYTHON_GIL=0` after that warning is not a fix. It is a dare. The module told you it is not safe. Believe it.

What about the stack you already run? On this machine, current NumPy, pandas, SciPy, Pydantic, and FastAPI imported clean: `gil_enabled=False` after each. That is September 2026, these pins, this platform. It is not a character reference.

The scientific stack has free-threaded wheels now ([NumPy 2.1+](https://py-free-threading.github.io/tracking/), pandas 2.2.3+, SciPy 1.15+). "Has a wheel" is not the same as "scales under threads." Some paths still take internal locks. Some submodules lag. Pydantic (2.11+) and FastAPI are generally fine; they were never the GIL-bound CPU story anyway. I/O libraries do not care. The lock was never what made `await` work.

The failure mode is the private wheel, the pinned 18-month-old `.so`, the "works on 3.14" package that only shipped `cp314`. Look for the `t` in the ABI tag. Track the rest at [py-free-threading](https://py-free-threading.github.io/tracking/) and [free-threaded wheels](https://hugovk.github.io/free-threaded-wheels/).

## When you should not switch

Stay on default 3.14 when the work is I/O. Async already overlaps waits. Free-threading will not make your FastAPI handlers magically use four cores while they talk to Postgres.

Stay off it when the hot path is a native library that still serializes, or a wheel that re-enables the GIL. You will pay the single-thread tax and keep the lock.

Stay off it for single-threaded CLIs. 5–10% slower, zero parallelism, nothing to show for the pin.

Prefer processes — `ProcessPoolExecutor`, a fleet of workers — when isolation matters more than shared memory. Crash domains, native leaks, and "I do not want to audit thread safety" are still good reasons to pay pickle and RAM.

## When you should

Switch when the work is CPU-bound Python that already shares memory awkwardly across processes: parallel transforms, image or PDF pipelines, batch hashing, local tooling that fans out over files.

Switch when you control the dependency set. Greenfield services, internal workers, labs. Not the 40-wheel monolith you inherited.

Switch when you have measured *your* workload on `3.14t` with the detector green after every import. The table above is mine. Yours will lie differently.

## Production checklist

- Pin `3.14t` in `.python-version`, uv, and the image. Official `python:3.14` Hub tags still ship the GIL. There is no `FROM python:3.14t`; install the free-threaded interpreter with uv (see the Dockerfile in this repo) or build with `--disable-gil`.
- Smoke-test `sys._is_gil_enabled() is False` in CI after application imports, not before them.
- Audit wheels for `cp314t`. Re-run the detector whenever the lockfile moves.
- Review thread safety. The GIL used to serialize bytecode; it was a crude lock you did not ask for. `dict` / `list` / `set` have internal locks today, and CPython does not promise they always will. Use `threading.Lock` around shared mutable state.
- Benchmark the real job. A parse loop that scales 4× is an existence proof, not a capacity plan.

## What this isn't

This is not "delete `multiprocessing`." Processes still win when you want isolation, when the native library is a known GIL hog, or when you do not want to think about shared mutable state at 2am.

It is not a promise that NumPy, pandas, or SciPy will scale your existing `apply` the way this parse loop scaled. They imported clean on this machine. That means the lock stayed off, not that every C loop is now a free lunch.

It is not phase III. Default Python 3.14 still has the GIL. If your Dockerfile says `FROM python:3.14-slim`, you did not turn anything off. Official Hub tags do not ship `3.14t` yet. Pin the free-threaded interpreter yourself:

```dockerfile
# GIL-on (what Hub actually gives you)
FROM python:3.14-slim

# Free-threaded: install 3.14t with uv. There is no python:3.14t tag.
FROM debian:bookworm-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv python install 3.14t
```

The full image is in the repo. The `FROM` line is the part people will get wrong.

## Close

Free-threading in 3.14 is real. On this box, four threads finished CPU-bound Python in a quarter of the time. That is worth trying.

It is also a different ABI, a different image, and a dependency veto. One unmarked `.so` and you are back to one core, with a warning that looks like noise.

Try the lab on your hottest CPU path. Then tell me what broke.
