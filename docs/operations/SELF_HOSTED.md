# Self-hosted operations runbook

This document describes running PARTHA's documented Docker Compose stack
(API + PostgreSQL + Redis) as it exists today. It is operational guidance, not
a claim of production hardening — read [Limitations and security](../../README.md#limitations-and-security)
first.

## One command sequence

From a clean checkout, with Docker and Docker Compose installed:

```bash
npm run docker:config     # validate the Compose file resolves
npm run docker:up         # build and start api + postgres + redis
npm run docker:validate   # full clean-clone acceptance gate (see below); tears the stack down when done
```

`npm run docker:validate` (`scripts/validate-compose.mjs`) is the repeatable
acceptance gate for this stack. From a clean checkout it: brings the stack up,
waits for `/ready`, re-runs and verifies Alembic migrations (including a
downgrade/upgrade round trip and a percent-encoded `DATABASE_URL` password —
the [#110](https://github.com/Second-Origin/PARTHA/issues/110) regression),
registers two disposable users and proves owner isolation (a non-owner gets
`404`, never `403`, on another user's repository), runs a full analysis to a
sealed `ri.v1` snapshot, restarts the `api` container and confirms the
repository, analysis result, and sealed snapshot all survive with no orphaned
job rows, proves a `pg_dump`/`pg_restore` round trip preserves a sealed
snapshot, and checks `docker compose logs` for the secrets it created. It
always tears the stack down (`docker compose down -v`), and exits non-zero on
any assertion failure.

To bring the stack down without running the gate: `docker compose down -v`.

## Required environment variables

Outside `development`/`test`, the backend refuses to start unless these are
set (see `apps/backend/.env.example` for the full list with generation
commands):

| Variable | Requirement |
| --- | --- |
| `AUTH_SECRET_KEY` | Required, at least 32 characters. Signs access tokens. |
| `AI_ENCRYPTION_KEY` | Required, a valid Fernet key. Encrypts each user's AI provider API key at rest. |
| `DATABASE_URL` | `sqlite:///…`, `postgresql://…`, or `postgresql+psycopg://…`. Compose sets this from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`. A percent-encoded password (e.g. a literal `@` written as `%40`) is supported end-to-end, including by Alembic. |
| `REDIS_URL` | `redis://` or `rediss://`. Backs shared rate-limit budgets across API workers; Compose runs Redis for this. |
| `AI_EGRESS_MODE` | `hosted` (default, fail-safe) or `self_hosted`. See below. |
| `CORS_ORIGINS` | At least one valid `http(s)://` origin. No default that "just works" in production. |
| `AUTO_CREATE_TABLES` | Set `false` outside development/test so Alembic migrations are the sole source of schema truth (Compose already sets this). |

Optional, with working defaults: `AI_EGRESS_ALLOWED_BASE_URLS`,
`AI_EGRESS_ALLOWED_CIDRS` (only meaningful when `AI_EGRESS_MODE=self_hosted`),
`RATE_LIMIT_*`, `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS`,
`LOG_LEVEL`, `LOG_FORMAT`, `STORAGE_PATH`.

Compose-only, not read directly by the backend: `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB` (feed `DATABASE_URL`).

## Security boundaries

- **Authentication and owner isolation.** Every non-auth route requires a
  bearer access token; every repository, analysis, and intelligence resource
  is owner-scoped. A request for another owner's resource returns `404`, not
  `403` — it must not disclose that the resource exists.
- **Provider credentials.** Each user's AI provider API key is encrypted at
  rest with `AI_ENCRYPTION_KEY` (Fernet). It is never logged or returned in a
  response body.
- **AI egress allowlist and DNS pinning.** Outbound AI provider requests are
  restricted to a deployment-owned allowlist with DNS pinning against
  redirect and rebinding attacks. Read the
  [AI provider egress policy](../security/AI_PROVIDER_EGRESS.md) in full
  before configuring a custom or local (e.g. Ollama) provider endpoint —
  a local/internal endpoint requires `AI_EGRESS_MODE=self_hosted` plus an
  explicit administrator-owned base URL and CIDR allowlist; tenants cannot
  widen this themselves.
- **Do not expose the development configuration to the public internet.**
  The default Compose stack is local-development shaped (published
  `5432`/`6379` ports, no TLS termination, no reverse proxy, no rate-limit
  tuning for hostile traffic). Treat it as a trusted-network deployment
  behind your own network boundary, not an internet-facing service.
- Report vulnerabilities privately per [SECURITY.md](../../SECURITY.md) —
  never in a public issue.

## Unsupported deployment modes

PARTHA today is **pre-alpha, trusted-environment software**. The following
are explicitly not implemented or not hardened, and must not be assumed:

- Public, multi-tenant exposure of a single deployment to untrusted users.
- Private-repository secure connect with per-connection permissions and
  revocation — only public GitHub import and archive upload exist today.
- A separate analysis worker service or external job queue — analysis runs
  on an in-process daemon thread inside the API, one job at a time.
- Organization/workspace membership, roles, or audit logs.
- Self-service account recovery.
- Automated backup scheduling, retention policy, or a backup/restore
  operational runbook beyond the manual procedure below.
- Quotas, abuse controls, or production-grade monitoring beyond the
  structured JSON logs and `/ready`/`/health` endpoints.

## Backup and restore expectations

Sealed `ri.v1` repository-intelligence snapshots (`ri_snapshots`, `ri_nodes`,
`ri_edges`, `ri_assertions`, `ri_observations`, `ri_evidence`,
`ri_derivations`, `ri_diagnostics`) are stored entirely in PostgreSQL, the
same as every other durable record (`repositories`, `analysis_jobs`, `users`).
There is no separate blob store or external snapshot artifact to back up.

A standard `pg_dump`/`pg_restore` round trip of the PostgreSQL database
preserves sealed snapshots byte-for-byte — `npm run docker:validate` performs
exactly this round trip (dump the running database, restore into a scratch
database, and confirm a sealed snapshot's canonical graph hash is unchanged)
as part of its acceptance sequence. Example manual procedure against a
running Compose stack:

```bash
docker compose exec postgres pg_dump -U partha partha > backup.sql
# ... later, against a fresh database ...
docker compose exec -T postgres psql -U partha -d partha < backup.sql
```

There is no automated backup schedule, retention policy, or point-in-time
recovery tooling — operators must run and store their own dumps.
