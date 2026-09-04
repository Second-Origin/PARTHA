# Local development and troubleshooting

A single walkthrough for getting PARTHA running locally, running its test
suites, and resolving the failures a new contributor is most likely to hit.
It consolidates and cross-links the [root README](../README.md#run-partha-locally),
[CONTRIBUTING.md](../CONTRIBUTING.md#1-setup), and the
[backend](../apps/backend/README.md) and [frontend](../apps/frontend/README.md)
guides rather than duplicating them — follow those links for anything not
covered here.

## Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Python | 3.12 or 3.13 | Backend |
| Node.js | 22 | Frontend and workflow scripts |
| Git | Recent version | Checkout and public GitHub import |

There is no Docker Compose file for local development. A root [`Dockerfile`](../Dockerfile)
exists for single-service hosting (building the frontend and serving it from
the same FastAPI process), but day-to-day development runs the backend and
frontend as two separate local processes, described below.

## 1. Clone and start the backend

```bash
git clone https://github.com/Second-Origin/PARTHA.git
cd PARTHA

cd apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
cd ../..

npm run dev:backend
```

The API starts at `http://localhost:8000`. Confirm it is up with `curl http://localhost:8000/ready`
(expects `{"status":"ready", ...}`) or open `http://localhost:8000/docs` for the OpenAPI UI.

No `.env` file is required — every setting has a working default. Local
development defaults to SQLite at `apps/backend/.local/partha.db` and local
filesystem storage at `apps/backend/.local/storage`, so nothing else needs to
be installed or running. Copy `apps/backend/.env.example` to `.env` only if
you need to change one specific value.

## 2. Start the frontend

In a second terminal, from the repository root:

```bash
npm ci --prefix apps/frontend
npm run dev:frontend
```

Open `http://localhost:5173`. There is no seeded account or sample
repository — register a new local account through the UI, then add a
repository (upload an archive or import a public GitHub repository over
HTTPS) and start analysis.

`VITE_API_URL` sets the backend origin the frontend calls; leave it unset to
use the default (`http://localhost:8000`). It is inlined at build time, so
changing it requires restarting the dev server.

## 3. Running the test suites and checks

```bash
# Backend (from apps/backend, with its venv active)
python -m pytest

# Backend static analysis (needs apps/backend/requirements-dev.txt installed first)
ruff check app scripts tests
ruff format --check app scripts tests
mypy app scripts

# Frontend, from the repository root
npm --prefix apps/frontend run test    # vitest
npm run lint:frontend                  # eslint
npm run build:frontend                 # tsc -b && vite build -- type errors surface here, not in lint

# API contract: regenerate the frontend's DTOs from the live FastAPI schema
npm run generate:api-contract
npm --prefix apps/frontend run generate:api-contract -- --check   # fails if the checked-in file is stale

# Disposable fixtures + Playwright browser journeys
npm run test:e2e
```

Backend tests default to a per-test SQLite database and an in-memory rate
limiter, so nothing external is required to run the full suite. Two specific
tests opt into real services and skip cleanly without them:

- the PostgreSQL migration round-trip and refresh-token concurrency test skip
  with `set PARTHA_TEST_PG_URL to run the Postgres concurrency test` unless
  `PARTHA_TEST_PG_URL` is set to a real Postgres connection string;
- the Redis-backed rate-limiter tests skip with
  `set PARTHA_TEST_REDIS_URL to run the Redis backend test` unless
  `PARTHA_TEST_REDIS_URL` is set.

CI provides both services and runs everything; neither is required for local
development.

## Troubleshooting

**Backend won't start: `ERROR: [Errno 48] error while attempting to bind on address ('127.0.0.1', 8000): address already in use`**
Something else (often a previous `dev:backend` you forgot to stop) is already
listening on 8000. Stop it, or start on a different port:
`python -m uvicorn app.main:app --reload --reload-dir app --port 8001` (and
point the frontend at it with `VITE_API_URL=http://localhost:8001`).

**Frontend silently starts on a different port than 5173**
Vite does not fail on a port conflict — it logs `Port 5173 is in use, trying
another one...` and starts on the next free port (typically 5174) instead.
Check the terminal output for the actual `Local:` URL it printed rather than
assuming 5173.

**Backend refuses to start with a message naming a table that "already exists"**
This is local database drift: `AUTO_CREATE_TABLES` (on by default in
`development`/`test`) built a table directly from the models without ever
recording it as an applied Alembic migration, so a later real migration for
that same table fails when it tries to create it again. The startup error
names the conflicting table(s) and the exact recovery — see
[backend README § Local database schema drift](../apps/backend/README.md#local-database-schema-drift-developmenttest-only)
for the full explanation and the `alembic stamp` / `alembic upgrade head`
commands to run.

**`ruff: command not found` / `mypy: command not found` when running static analysis**
The runtime install (`pip install -e .`) deliberately excludes development
tooling. Install it first: `pip install -r apps/backend/requirements-dev.txt`
(see [backend README § Static analysis](../apps/backend/README.md#static-analysis)).

**`npm --prefix apps/frontend run generate:api-contract -- --check` fails with `Generated API contract is stale at character N. Run \`npm run generate:api-contract\`.`**
A backend schema change (a new/changed Pydantic model or route) was made
without regenerating the frontend's DTOs. Run `npm run generate:api-contract`
from the repository root, review the diff to `generated.ts`, and commit it
alongside the backend change that caused it.

**A test needing PostgreSQL or Redis is skipped instead of failing**
That's expected locally — see the skip reasons in §3 above. It is not a sign
of a broken local setup; CI runs those tests against real services.

## Reporting a reproducible issue

Search open issues first to avoid a duplicate. For a bug, use the **Bug
Report** template in [`.github/ISSUE_TEMPLATE/`](../.github/ISSUE_TEMPLATE/)
and include exact reproduction steps (route, endpoint, input repository,
commands run), expected versus actual behaviour, and any relevant log output
— see [CONTRIBUTING.md § Choosing a template](../CONTRIBUTING.md#choosing-a-template).
**Never file a security vulnerability as a public issue** — report it
privately through [SECURITY.md](../SECURITY.md) instead. For a question that
isn't yet a confirmed bug, ask on [Discord](https://discord.gg/qvk9DcxDA)
first.
