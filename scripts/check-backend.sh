#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"
./.venv/bin/python -m pytest
