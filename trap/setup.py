from setuptools import Extension, setup

setup(
    name="gil-trap",
    version="0.1.0",
    description="Unmarked C extension that re-enables the GIL on free-threaded Python.",
    ext_modules=[Extension("gil_trap", sources=["gil_trap.c"])],
)
