# PARTHA Backend

FastAPI backend for repository ingestion, parsing, architecture analysis, dependency graphing, and engineering review.

This app lives at `apps/backend` in the PARTHA monorepo.

## Local Development

```bash
cd apps/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m uvicorn app.main:app --reload
```

By default, local development uses SQLite at `.local/partha.db` and storage at `.local/storage` so the app can start without services. Docker Compose injects PostgreSQL, Redis, and container storage settings separately.

Useful system endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Lightweight liveness check with the current environment label. |
| `GET /ready` | Readiness check for database connectivity and configured storage writability. |

Backend logs default to human-readable text. Set `LOG_FORMAT=json` for structured logs in containers or hosted environments.

## Docker

```bash
cd ../..
docker compose up --build
```

Swagger UI is available at `http://localhost:8000/docs`.

## First Import Flow

```bash
curl -X POST http://localhost:8000/repositories/github \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/octocat/Hello-World"}'
```
