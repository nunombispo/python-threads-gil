# Official `python:3.14` Hub tags still ship with the GIL.
# There is no `FROM python:3.14t`. Pin the free-threaded interpreter
# with uv so CI and images cannot silently fall back to 3.14.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml .python-version benchmark.py gil_detector.py ./

ENV UV_LINK_MODE=copy
RUN uv python install 3.14t

CMD ["uv", "run", "--python", "3.14t", "python", "benchmark.py"]
