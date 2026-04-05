#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/3] Installing project in editable mode (offline-safe)..."
if python -m pip install -e . --no-build-isolation >/tmp/bootstrap_pip.log 2>&1; then
  echo "pip editable install: ok"
else
  echo "pip editable install failed, falling back to setup.py develop"
  python setup.py develop >/tmp/bootstrap_setup.log 2>&1
  echo "setup.py develop: ok"
fi

echo "[2/3] Syntax check..."
python -m compileall app >/tmp/bootstrap_compile.log 2>&1

echo "[3/3] Runtime import smoke check..."
python - <<'PY'
from app.main import app
print(app.title)
PY

echo "Bootstrap completed successfully."
