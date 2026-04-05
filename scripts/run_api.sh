#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-1}"

if ! python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "FastAPI/uvicorn are missing. Installing prod dependencies..."
  python -m pip install -e .[prod]
fi

echo "Starting API on http://${HOST}:${PORT}"
echo "Swagger: http://${HOST}:${PORT}/docs"
echo "OpenAPI: http://${HOST}:${PORT}/openapi.json"

if [[ "$RELOAD" == "1" ]]; then
  exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
fi

exec uvicorn app.main:app --host "$HOST" --port "$PORT"
