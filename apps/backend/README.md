# PARTHA Backend

FastAPI backend for repository ingestion, Repository Intelligence, architecture and dependency analysis, engineering review, documentation generation, exports, and AI orchestration.

This app lives at `apps/backend` in the PARTHA monorepo. For contributor workflow and engineering rules, see the root [CONTRIBUTING.md](../../CONTRIBUTING.md). For what the engine actually extracts, see [Repository Intelligence](../../docs/architecture/REPOSITORY_INTELLIGENCE.md).

## Local development

Requires Python 3.12 or 3.13 (`>=3.12,<3.14`).

```bash
cd apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m uvicorn app.main:app --reload
```

Or from the repository root: `npm run dev:backend` (prefers `apps/backend/.venv`, falls back to `python`).

Local development defaults to SQLite at `.local/partha.db` and storage at `.local/storage`, so the app starts with no PostgreSQL and no Redis. **No `.env` file is required** — every setting has a working default. Copy `.env.example` to `.env` only to change one.

`AUTH_SECRET_KEY` falls back to a fixed insecure value when `APP_ENV` is `development` or `test`. Outside those environments the app **refuses to start** without an explicit secret of at least 32 characters:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Tests

```bash
python -m pytest          # from apps/backend
npm run test:backend      # from the repository root
```

Tests use per-test SQLite and the in-memory rate limiter by default. When `PARTHA_TEST_PG_URL` is set, the migration round trip runs against a fresh temporary PostgreSQL database and the PostgreSQL refresh-token concurrency test is enabled; without it, migrations fall back to SQLite and the concurrency test skips. Redis integration tests skip unless `PARTHA_TEST_REDIS_URL` is set. CI provides both services.

## Migrations

```bash
alembic upgrade head
alembic downgrade -1
```

`AUTO_CREATE_TABLES` defaults to true in `development`/`test` and false elsewhere, so non-dev environments rely on migrations rather than `create_all`. Every migration must downgrade cleanly — `tests/test_migrations.py` enforces it.

## System endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process liveness, with the current environment label. |
| `GET /ready` | Readiness: database connectivity and writable storage. Returns 503 when a check fails. |
| `GET /metrics` | Plain-text counters: request volume, status families, routes, cumulative duration, rate-limit counters. |
| `GET /docs` | OpenAPI / Swagger UI. |

Logs default to human-readable text; set `LOG_FORMAT=json` for structured logs in containers. Structured-log extras are redacted for keys containing `api_key`, `apikey`, `authorization`, `password`, `secret`, or `token`. Every response carries `X-Request-ID`; an inbound `X-Request-ID` is preserved.

## Authentication

`/auth` provides register, login, refresh, logout, and `/auth/me`. Passwords are hashed with Argon2; access tokens are HS256; refresh tokens rotate on every use, live in an httpOnly cookie, and reuse of a spent token revokes the whole family.

**The API does not currently require authentication.** A presented Bearer token is always validated strictly — a bad token is a 401, never a silent downgrade — but a request with *no* token falls back to a shared seed user. Additionally, only the `/repositories` routes are owner-scoped; the analysis, AI, documentation, and export routes resolve a repository by ID with no owner check. Do not expose this backend to untrusted users. See [SYSTEM_OVERVIEW.md](../../docs/architecture/SYSTEM_OVERVIEW.md#current-architectural-limitations).

## Docker

```bash
cd ../..
docker compose up --build
```

Compose runs the API against PostgreSQL and Redis. It does not run the frontend.

## First import

```bash
curl -X POST http://localhost:8000/repositories/github \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/octocat/Hello-World"}'
```

Only public GitHub HTTPS URLs are accepted. Ingestion and analysis run **synchronously** inside the request — a large repository will block until the clone, parse, and analysis finish.

Repository responses include first-class source identity:

```json
{
  "revision": {
    "kind": "git",
    "value": "0123456789abcdef0123456789abcdef01234567",
    "ref": "refs/heads/main"
  },
  "commitSha": "0123456789abcdef0123456789abcdef01234567"
}
```

For uploads, `kind` is `upload`, `value` is `sha256:<64 lowercase hex>`, and `ref` is `null`. `commitSha` remains a compatibility alias of `revision.value`; authoritative identity lives in the indexed revision columns, not `repo_metadata`. Re-importing the same source at a new commit or a changed archive creates a new repository revision. Snapshot query endpoints are not part of #87/#88 and remain #92.
