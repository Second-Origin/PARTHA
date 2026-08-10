# Scripts

Local workflow helpers. Prefer the root `package.json` scripts for common tasks — these are what those scripts call.

| Script | Purpose | Invoked by |
| --- | --- | --- |
| `backend-python.mjs` | Runs a backend Python command through `apps/backend/.venv` when present, falling back to `python`. | `npm run dev:backend`, `npm run start:backend`, `npm run test:backend` |
| `seed-prototype-fixtures.mjs` | Idempotently recreates the disposable Architecture/Review/Insights fixture repositories for one fixture account and writes a mode-0600 temporary manifest. | `npm run fixtures:prototype`, or the acceptance runner |
| `run-prototype-acceptance.mjs` | Starts isolated backend/frontend processes on free loopback ports, seeds fixtures, forwards optional Playwright CLI filters, runs the selected browser journeys, and removes temporary database/storage state. | `npm run test:prototype`, `npm run test:accessibility` |
| `start-backend.sh` | Starts the backend with uvicorn on `0.0.0.0:8000`. Same venv preference as above; override with `PYTHON=…`. | Directly, or from a process manager |
| `check-backend.sh` | Runs the backend test suite (`pytest`). Same venv preference; override with `PYTHON=…`. | Directly |

The two shell scripts are standalone equivalents of the Node helpers, for environments where invoking `node` first is inconvenient.

`npm run test:prototype` is the one-command browser gate after dependencies are installed. It
installs Chromium if needed; CI runs the same acceptance runner and uploads its report.
`npm run test:accessibility` reuses that stack and runs only the WCAG baseline journeys. The
runner uses `apps/backend/.venv` on Windows or POSIX when present and the fixture seeder uses
Python's standard-library ZIP writer, so neither command depends on a system `zip` executable.
