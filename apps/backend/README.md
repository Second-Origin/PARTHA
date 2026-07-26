# PARTHA Backend

FastAPI backend for repository ingestion, Repository Intelligence, architecture and dependency analysis, engineering review, documentation generation, exports, and AI orchestration.

All repository-derived product reads resolve an owner-scoped sealed `ri.v1`
snapshot matching the repository's current revision. Documentation, exports,
and free-form AI context do not read legacy JSON or rebuild from repository
files. A missing or stale snapshot is unavailable (404), with no fallback.
Historical `repo_metadata["intelligence"]` values may remain stored but are
ignored. Free-form AI additionally requires a configured provider and receives
no source-file contents.

This app lives at `apps/backend` in the PARTHA monorepo. For contributor workflow and engineering rules, see the root [CONTRIBUTING.md](../../CONTRIBUTING.md). For what the engine actually extracts, see [Repository Intelligence](../../docs/architecture/REPOSITORY_INTELLIGENCE.md).

## Local development

Requires Python 3.12 or 3.13 (`>=3.12,<3.14`).

```bash
cd apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m uvicorn app.main:app --reload --reload-dir app
```

Or from the repository root: `npm run dev:backend` (prefers `apps/backend/.venv`, falls back to `python`).

`--reload-dir app` restricts the reload watcher to backend source. Without it, uvicorn watches the whole `apps/backend` working directory, including `.local/storage` — the local filesystem storage the app itself writes to during ingestion and analysis — so an in-progress analysis job's own writes could trigger a server restart and drop open requests (#161). Migration files under `alembic/` are applied with an explicit `alembic upgrade` command, not hot-reloaded, so they are intentionally not watched.

Local development defaults to SQLite at `.local/partha.db` and storage at `.local/storage`, so the app starts with no PostgreSQL and no Redis. **No `.env` file is required** — every setting has a working default. Copy `.env.example` to `.env` only to change one.

### SQLite concurrency (development only)

The durable analysis worker (a background thread) and API request handlers read and write the same SQLite file concurrently. Every SQLite connection is opened with `PRAGMA journal_mode=WAL` and a 5-second `PRAGMA busy_timeout` (`app/core/database.py`, a no-op on PostgreSQL): WAL lets a reader always see the last committed snapshot without waiting on an in-progress writer, and the busy timeout bounds the remaining writer-vs-writer wait instead of failing immediately (#162). This does not extend to multiple *processes* sharing one SQLite file — that remains PostgreSQL's job; Compose already runs Postgres for exactly this reason. The analysis worker's own per-stage transaction boundaries (why a stage's facts are flushed but not committed until the stage checkpoint) are documented directly in `app/workers/analysis_worker.py`'s module docstring and were deliberately left unchanged — restructuring them risks the job-recovery guarantees (leases, retries, stale-worker takeover) that same docstring exists to protect, and WAL removes the actual reader-blocking symptom without needing to.

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

### Local database schema drift (development/test only)

`create_all` creates any table missing from the database but never alters an existing one and never advances the `alembic_version` stamp, so an existing local database can silently drift from the code after a schema-changing merge — without a check, that surfaces later as an opaque `IntegrityError`/`OperationalError` on whatever request happens to touch the drifted column or table, not as a clear migration error.

To prevent that, startup in `development`/`test` compares the database's Alembic revision against head (`app/core/schema_sync.py`, wired into `app.main`'s lifespan):

- **Up to date** — no action.
- **Behind head, no physical conflict** — upgrades the database automatically (`alembic upgrade head`, run through the same in-process API `tests/test_migrations.py` uses, not the CLI) and logs exactly what it did. This is the common case after pulling a schema-changing merge.
- **Behind head, but a pending migration's table already exists physically** — refuses to start rather than attempt an upgrade that would crash with "table already exists". This happens when `AUTO_CREATE_TABLES` built a table without ever advancing the stamp. The startup error names the conflicting table(s) and the exact recovery:

  ```bash
  cd apps/backend && .venv/bin/alembic stamp <revision>   # mark migrations already reflected physically as applied
  cd apps/backend && .venv/bin/alembic upgrade head        # apply whatever genuinely remains pending
  ```

- **A brand-new, empty database** — `create_all` builds every table directly from the current models (by definition already head's shape), then the database is stamped at head directly; no migration body runs and no drift check is needed.

Production/staging are unaffected: this check is a no-op outside `development`/`test`, so those environments keep relying on an operator running migrations explicitly.

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

Every non-public API route requires a valid Bearer token. Repository resolution is
owner-scoped in the service layer across analysis and all product consumers, so
one account cannot query another account's repository or snapshots.

## Docker

```bash
cd ../..
docker compose up --build
```

Compose runs the API against PostgreSQL and Redis. It does not run the frontend.

## AI provider egress

AI provider traffic is centrally checked at configuration save time and again
immediately before every outbound request. `AI_EGRESS_MODE=hosted` is the safe
default: fixed cloud providers retain their code-owned HTTPS origins and no
tenant-configurable endpoint is enabled. To use a trusted local or internal
Ollama endpoint, a deployment administrator must set `AI_EGRESS_MODE=self_hosted`
and provide both an exact `AI_EGRESS_ALLOWED_BASE_URLS` entry and matching
`AI_EGRESS_ALLOWED_CIDRS` entry. These are not tenant settings.

The sender validates every DNS answer, pins the HTTP connection to a validated
IP while preserving the original Host/SNI name, ignores ambient proxy settings,
and rejects redirects. Compose keeps PostgreSQL and Redis on an internal data
network, but production still needs an independent firewall, egress proxy,
cloud egress rule, or mesh policy. See [AI provider egress policy](../../docs/security/AI_PROVIDER_EGRESS.md)
for configuration, rollout, and migration details.

## First import

```bash
curl -X POST http://localhost:8000/repositories/github \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/octocat/Hello-World"}'
```

Only public GitHub HTTPS URLs are accepted. Clone/archive extraction and initial
file-tree parsing finish before the import response. Submit analysis separately;
the start endpoint returns immediately after durably enqueueing the work:

```bash
curl -X POST http://localhost:8000/analysis/<repository-id>/start \
  -H "Authorization: Bearer <access-token>"
```

### Analysis job lifecycle

Analysis jobs have exactly five observable states: `queued`, `running`,
`completed`, `failed`, and `cancelled`. The API-process lifespan starts a daemon
worker thread; no separate worker deployment is required. Progress advances only
at completed pipeline stages. Failed work retries with bounded exponential
backoff up to the job's attempt limit, then becomes `failed`.

`POST /analysis/{repository_id}/cancel` cancels queued work immediately and
requests cooperative cancellation of running work. Workers renew a guarded
database lease periodically during stages as well as at stage boundaries, so
long-running analysis remains owned and cancellation is noticed promptly.
Startup and periodic stale job sweeps reclaim expired leases, fail orphaned
building snapshots, and either
requeue or fail the job within its attempt budget. If a process dies after a
snapshot was sealed but before the job completion commit, the sweep reconciles
the job to `completed` without producing a duplicate snapshot.

Operational settings are `ANALYSIS_WORKER_AUTOSTART`,
`ANALYSIS_JOB_POLL_INTERVAL_SECONDS`, and `ANALYSIS_JOB_LEASE_SECONDS`.

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

For uploads, `kind` is `upload`, `value` is `sha256:<64 lowercase hex>`, and `ref` is `null`. `commitSha` remains a compatibility alias of `revision.value`; authoritative identity lives in the indexed revision columns, not `repo_metadata`. Re-importing the same source at a new commit or a changed archive creates a new repository revision.

## Snapshot-backed product endpoints

Architecture, Engineering Review, and Insights resolve the authenticated
owner's latest sealed `ri.v1` snapshot and bind every response to its exact
repository revision and snapshot identity.

- `GET /analysis/{repository_id}/architecture` returns the normalized graph and
  provenance manifest.
- `GET /analysis/{repository_id}/review` returns
  `engineering-review.v2`: deterministic, evidence-linked findings and explicit
  assessed/not-assessed category states. It emits no score, grade, or invented
  metric.
- `GET /analysis/{repository_id}/insights` returns `repository-insights.v1`:
  defined snapshot counts, breakdowns, diagnostics, extractor coverage, and
  provenance. Change history is explicitly unavailable until comparable
  snapshots are implemented.
- `GET /analysis/{repository_id}/dependencies` returns `dependency-graph.v2`:
  sealed-snapshot dependency nodes, declarations (with manifest path and line
  span merged across manifests, #156), and resolved `depends_on` edges. It
  does not provide vulnerability or outdated-package scanning.
