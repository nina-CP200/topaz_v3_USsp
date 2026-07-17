#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PID=""
FRONTEND_PID=""

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

cleanup() {
  trap - EXIT INT TERM
  if [[ -z "$FRONTEND_PID" && -z "$BACKEND_PID" ]]; then
    return
  fi
  echo
  echo "Stopping Topaz US development services..."
  if [[ -n "$FRONTEND_PID" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  wait "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
}

for command in uv curl lsof; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

if port_in_use "$BACKEND_PORT"; then
  echo "Backend port $BACKEND_PORT is already in use." >&2
  echo "Stop that process or run: BACKEND_PORT=8001 ./dev.sh" >&2
  exit 1
fi

if port_in_use "$FRONTEND_PORT"; then
  echo "Frontend port $FRONTEND_PORT is already in use." >&2
  echo "Stop that process or run: FRONTEND_PORT=5174 ./dev.sh" >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
  echo "Frontend dependencies are missing. Run ./setup.sh first." >&2
  exit 1
fi

trap cleanup EXIT INT TERM

echo "Starting FastAPI on http://127.0.0.1:$BACKEND_PORT"
uv run uvicorn backend.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

echo "Starting React on http://127.0.0.1:$FRONTEND_PORT"
(
  cd "$ROOT_DIR/frontend"
  exec env VITE_API_TARGET="http://127.0.0.1:$BACKEND_PORT" ./node_modules/.bin/vite --host 127.0.0.1 --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

backend_ready=0
frontend_ready=0
for _ in $(seq 1 30); do
  if [[ "$backend_ready" -eq 0 ]] && curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    backend_ready=1
  fi
  if [[ "$frontend_ready" -eq 0 ]] && curl -fsS "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1; then
    frontend_ready=1
  fi
  if [[ "$backend_ready" -eq 1 && "$frontend_ready" -eq 1 ]]; then
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "A development service exited during startup." >&2
    exit 1
  fi
  sleep 0.5
done

if [[ "$backend_ready" -ne 1 || "$frontend_ready" -ne 1 ]]; then
  echo "Development services did not become ready in time." >&2
  exit 1
fi

echo
echo "Topaz US development environment is ready."
echo "App:     http://127.0.0.1:$FRONTEND_PORT"
echo "API:     http://127.0.0.1:$BACKEND_PORT"
echo "API docs: http://127.0.0.1:$BACKEND_PORT/docs"
echo "Press Ctrl+C to stop both services."

if [[ "${NO_OPEN:-0}" != "1" ]]; then
  open "http://127.0.0.1:$FRONTEND_PORT"
fi

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

echo "A development service stopped unexpectedly." >&2
exit 1
