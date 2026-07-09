#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"
PYTHON_BIN="${PYTHON:-./.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" -m pytest
