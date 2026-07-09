#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"
PYTHON_BIN="${PYTHON:-./.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python"
fi

exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
