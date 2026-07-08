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

By default, local development uses SQLite at `.local/partha.db` so the app can start without services. Docker Compose uses PostgreSQL and Redis.

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
