#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"
exec ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
