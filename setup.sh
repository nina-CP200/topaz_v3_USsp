#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Topaz US setup ==="
if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment..."
  uv venv
fi

echo "Installing Python dependencies..."
uv pip install -r requirements.txt

echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

mkdir -p data/raw/us_history

echo ""
echo "Setup complete."
echo "Run ./start.sh to build the frontend and start the local app."
