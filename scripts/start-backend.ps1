# Starts the PARTHA backend (FastAPI) on http://localhost:8000
# Usage (from repo root):  powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
$ErrorActionPreference = "Stop"

$backend = Join-Path $PSScriptRoot "..\apps\backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Backend venv not found at $python. Create it first: python -m venv apps/backend/.venv; apps/backend/.venv/Scripts/python.exe -m pip install -e apps/backend"
    exit 1
}

Set-Location $backend
& $python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
