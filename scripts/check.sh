#!/bin/sh
set -eu

python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -v

if command -v ruff >/dev/null 2>&1; then
    ruff check .
    ruff format --check .
fi

if command -v mypy >/dev/null 2>&1; then
    mypy
fi

