#!/bin/bash
set -e
cd "$(dirname "$0")/../frontend"

npm run dev -- --host 127.0.0.1 --port "${PORT:-5173}"

