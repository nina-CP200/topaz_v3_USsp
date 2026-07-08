#!/bin/bash
set -e
cd "$(dirname "$0")/.."

uv run uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8000}" --reload

