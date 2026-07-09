# Scripts

Local helper scripts live here. Prefer root `package.json` scripts for common workflows.

| Script | Purpose |
| --- | --- |
| `backend-python.mjs` | Runs backend Python commands through `apps/backend/.venv` when present, with `python` fallback. |
| `validate-compose.mjs` | Validates Docker Compose config, starts the stack, waits for `/ready`, and tears the stack down. |
