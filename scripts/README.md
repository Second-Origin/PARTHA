# Scripts

Local workflow helpers. Prefer the root `package.json` scripts for common tasks — these are what those scripts call.

| Script | Purpose | Invoked by |
| --- | --- | --- |
| `backend-python.mjs` | Runs a backend Python command through `apps/backend/.venv` when present, falling back to `python`. | `npm run dev:backend`, `npm run start:backend`, `npm run test:backend` |
| `validate-compose.mjs` | Validates the Docker Compose config, starts the stack, waits for `/ready`, then tears it down. | `npm run docker:validate` |
| `start-backend.sh` | Starts the backend with uvicorn on `0.0.0.0:8000`. Same venv preference as above; override with `PYTHON=…`. | Directly, or from a container/process manager |
| `check-backend.sh` | Runs the backend test suite (`pytest`). Same venv preference; override with `PYTHON=…`. | Directly |

The two shell scripts are standalone equivalents of the Node helpers, for environments where invoking `node` first is inconvenient.
