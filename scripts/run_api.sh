#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-1}"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Python is not installed (or not in PATH)." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "FastAPI/uvicorn are missing. Installing prod dependencies..."
  "$PYTHON_BIN" -m pip install -e .[prod]
fi

echo "Using Python interpreter: ${PYTHON_BIN}"
echo "Starting API on http://${HOST}:${PORT}"
echo "Swagger: http://${HOST}:${PORT}/docs"
echo "OpenAPI: http://${HOST}:${PORT}/openapi.json"

if [[ "$RELOAD" == "1" ]]; then
  exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
fi

exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
