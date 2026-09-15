# The GIL Is Optional. Your Dependencies Aren’t.

Companion lab for the article in [`article.md`](./article.md).

Python 3.14 made the free-threaded build officially supported ([PEP 779](https://peps.python.org/pep-0779/)). It is still a **separate interpreter** (`3.14t`), not a flag on default 3.14. Threads only speed up CPU-bound work if every native extension has opted in. Import a C module that hasn't, and the GIL comes back on for the rest of the process.

This repo is the copy-paste lab: a stdlib-only threaded benchmark, a GIL detector, and a tiny unmarked C extension that reproduces the silent re-enable.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Linux or macOS with a free-threaded CPython build available (`uv python list 3.14t`)

```bash
uv python install 3.14 3.14t
uv python pin 3.14t
```

`.python-version` pins `3.14+freethreaded` so `uv run` in this project cannot silently fall back to the GIL build. `requires-python` in `pyproject.toml` stays `>=3.14` — the `t` suffix is a build variant, not a language version.

## Run the benchmark

Same CPU-bound workload, 1 thread vs N threads, two interpreters. Use `--isolated` and `3.14+gil` so the pin in `.python-version` does not swallow the GIL comparison.

```bash
uv run --no-project --isolated --python 3.14+gil python benchmark.py
uv run --no-project --isolated --python 3.14t python benchmark.py
```

Or the whole lab:

```bash
chmod +x run_lab.sh
./run_lab.sh
```

The workload is pure-Python parse-and-fold on purpose. Libraries that drop the GIL from C would fake a speedup on default 3.14.

### Results on this machine

4 CPUs, CPython 3.14.5, 2,000,000 rows split across threads, best of 3:

| Build | GIL | 1 thread | 4 threads | Speedup |
| --- | --- | --- | --- | --- |
| 3.14 (`3.14+gil`) | on | 1.210 s | 2.133 s | 0.57× |
| 3.14t | off | 1.174 s | 0.320 s | 3.67× |

Default 3.14: four threads were slower than one — contention for the lock. 3.14t: about 3.7× on four cores. That near-linear number is the lab ceiling (embarrassingly parallel, no shared mutable state), not a production promise.

## Audit imports

```bash
uv run --no-project --isolated --python 3.14t python gil_detector.py
uv run --no-project --isolated --python 3.14t python gil_detector.py json hashlib
uv run --no-project --isolated --python 3.14t python gil_detector.py numpy pandas pydantic fastapi
```

On this machine, current NumPy, pandas, SciPy, Pydantic, and FastAPI stayed `gil_enabled=False` after import. That is not a lifetime guarantee. Pin versions and re-run the detector.

## The gotcha that kills the story

`trap/` is a C extension that does **not** declare `Py_MOD_GIL_NOT_USED`. Importing it on 3.14t re-enables the GIL:

```bash
uv run --no-project --isolated --python 3.14t --with ./trap python gil_detector.py gil_trap
```

Expected:

```
before imports               gil_enabled=False
gil_trap                     gil_enabled=True  <-- GIL re-enabled
                             warning: The global interpreter lock (GIL) has been enabled to load module 'gil_trap' ...
```

`PYTHON_GIL=0` after that warning is not a fix. The module told you it is not safe.

Track ecosystem wheels at [py-free-threading](https://py-free-threading.github.io/tracking/) and [free-threaded wheels](https://hugovk.github.io/free-threaded-wheels/).

## Docker

Official Hub tags still ship GIL-on 3.14. There is no `FROM python:3.14t`. The Dockerfile installs 3.14t with uv:

```bash
docker build -t python-threads-gil .
docker run --rm python-threads-gil
```

## Layout

| Path | Role |
| --- | --- |
| [`article.md`](./article.md) | Publish-ready post |
| [`benchmark.py`](./benchmark.py) | Stdlib-only 1 vs N thread CPU benchmark |
| [`gil_detector.py`](./gil_detector.py) | Import modules; watch for a GIL flip |
| [`trap/`](./trap/) | Unmarked C extension that re-enables the GIL |
| [`Dockerfile`](./Dockerfile) | uv + 3.14t image |
| [`run_lab.sh`](./run_lab.sh) | One-shot GIL vs 3.14t + trap demo |
