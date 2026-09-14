#!/usr/bin/env python3
"""Import modules one by one and watch for a silent GIL re-enable.

Start on a free-threaded interpreter. If a C extension has not opted in,
importing it can turn the GIL back on for the rest of the process.

    uv run --python 3.14t python gil_detector.py
    uv run --python 3.14t python gil_detector.py json hashlib
    uv run --python 3.14t python gil_detector.py numpy pandas pydantic
"""

from __future__ import annotations

import argparse
import importlib
import sys
import sysconfig
import warnings


def gil_on() -> bool:
    if not hasattr(sys, "_is_gil_enabled"):
        raise SystemExit("sys._is_gil_enabled() is missing; need Python 3.13+")
    return bool(sys._is_gil_enabled())


def report(label: str, before: bool) -> None:
    after = gil_on()
    flipped = (not before) and after
    flag = "  <-- GIL re-enabled" if flipped else ""
    print(f"{label:<28} gil_enabled={after}{flag}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit imports for a free-threaded GIL flip"
    )
    parser.add_argument("modules", nargs="*", help="module names to import")
    args = parser.parse_args()

    print(f"Python          {sys.version.splitlines()[0]}")
    print(f"Py_GIL_DISABLED {sysconfig.get_config_var('Py_GIL_DISABLED')}")
    report("before imports", gil_on())
    print()

    if not args.modules:
        print("Pass module names to audit, e.g. numpy pandas pydantic")
        raise SystemExit(0)

    for name in args.modules:
        before = gil_on()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                importlib.import_module(name)
            except Exception as exc:
                print(f"{name:<28} IMPORT FAILED: {type(exc).__name__}: {exc}")
                continue
            report(name, before)
            for warning in caught:
                message = str(warning.message)
                if "gil" in message.lower():
                    print(f"{'':28} warning: {message}")

    print()
    print(f"{'after all imports':<28} gil_enabled={gil_on()}")


if __name__ == "__main__":
    main()
