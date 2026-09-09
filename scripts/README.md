# Scripts

Local workflow helpers. Prefer the root `package.json` scripts for common tasks — these are what those scripts call.

| Script | Purpose | Invoked by |
| --- | --- | --- |
| `backend-python.mjs` | Runs a backend Python command through `apps/backend/.venv` when present, falling back to `python`. | `npm run dev:backend`, `npm run start:backend`, `npm run test:backend` |
| `seed-e2e-fixtures.mjs` | Idempotently recreates the disposable Architecture/Review/Insights fixture repositories for one fixture account and writes a mode-0600 temporary manifest. | `npm run fixtures:e2e`, or the acceptance runner |
| `run-e2e-acceptance.mjs` | Starts isolated backend/frontend processes on free loopback ports, seeds fixtures, forwards optional Playwright CLI filters, runs the selected browser journeys, and removes temporary database/storage state. | `npm run test:e2e`, `npm run test:accessibility` |
| `start-backend.sh` | Starts the backend with uvicorn on `0.0.0.0:8000`. Same venv preference as above; override with `PYTHON=…`. | Directly, or from a process manager |
| `check-backend.sh` | Runs the backend test suite (`pytest`). Same venv preference; override with `PYTHON=…`. | Directly |
| `generate-api-contract.mjs` | Regenerates the frontend DTOs from the FastAPI OpenAPI schema using the pinned `openapi-typescript`. `--check` fails on drift instead of writing. | `npm run generate:api-contract`, CI **API Contract Drift** |
| `check-capabilities.py` | Validates the capability registry and the generated README block against `app/extraction/support_matrix.py`, so the published capability table cannot drift from the support matrices. | CI **Backend** |
| `apps/backend/scripts/approve_email.py` | **Operator tool for the registration gate.** Adds an email address to the `approved_emails` allowlist, which is what permits that address to register. There is deliberately no admin UI or API route for this. Approving the same address twice is a harmless no-op. | Maintainer, directly |
| `apps/backend/scripts/list_waitlist.py` | Lists landing-page waitlist signups, newest first (`--csv` for a spreadsheet). The owner's review step before deciding whom to approve next. | Maintainer, directly |
| `apps/backend/scripts/rehearse_migrations.py` | Creates disposable SQLite (or explicitly confirmed PostgreSQL) targets, exercises the Alembic clean chain and representative `0004` baseline, then removes the targets. | Maintainer runbook and backend test suite |
| `apps/backend/scripts/rehearse_backup_restore.py` | Proves a database + storage backup can be restored into a clean environment byte-for-byte and row-for-row, canonical graph hash included. Accepts no database URL: every target is one it created and removes again, even on failure. PostgreSQL is opt-in and needs `pg_dump`/`pg_restore`. | Maintainer runbook, [migration rehearsal doc](../docs/operations/DATABASE_MIGRATION_REHEARSAL.md) |
| `dependency-audit.mjs` | Runs the frontend dependency audit against the policy below and fails on a blocking finding. | CI **Frontend** |
| `dependency-audit.test.mjs` | Node test suite for the audit policy logic itself. | `node --test scripts/dependency-audit.test.mjs`, CI **Frontend** |
| `dependency-audit-policy.json` | Data, not a script: the reviewed-exception list the audit reads. Each entry carries a checkable reason and a `reviewBy` date, and the build fails once it expires — or if the advisory stops naming the package, the accepted version changes unreviewed, or the vulnerable code becomes reachable. Removing the dependency without removing its entry fails too, so acknowledgements cannot go stale silently. | `dependency-audit.mjs` |

The two shell scripts are standalone equivalents of the Node helpers, for environments where invoking `node` first is inconvenient.

The generated frontend contract at `apps/frontend/src/shared/services/api/generated.ts` and the
capability block in the root README are both build outputs. Edit their sources — the FastAPI
schema and `support_matrix.py` — and regenerate; CI fails on hand edits that drift.

`npm run test:e2e` is the one-command browser gate after dependencies are installed. It
installs Chromium if needed; CI runs the same acceptance runner and uploads its report.
`npm run test:accessibility` reuses that stack and runs only the WCAG baseline journeys. The
runner uses `apps/backend/.venv` on Windows or POSIX when present and the fixture seeder uses
Python's standard-library ZIP writer, so neither command depends on a system `zip` executable.
