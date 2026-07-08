#!/bin/bash
set -e
cd "$(dirname "$0")/.."

uv run python -m compileall -q topaz_us backend diagnostics tests
uv run python -m unittest discover -s tests
cd frontend
npm run build

