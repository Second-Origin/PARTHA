# PARTHA — Local Setup & Demo Guide

A practical guide to run PARTHA locally and give a clean 3–5 minute demo. Commands are Windows-first (PowerShell); macOS/Linux equivalents are noted where they differ.

## Prerequisites

| Tool | Version |
| --- | --- |
| Node.js | 22+ (bundled npm) |
| Python | 3.12 or 3.13 |
| Git | any recent version |

## One-time setup

From the repo root:

```powershell
# 1. Frontend deps
npm install --prefix apps/frontend

# 2. Backend venv + deps
python -m venv apps/backend/.venv
apps/backend/.venv/Scripts/python.exe -m pip install -e apps/backend
```

> macOS/Linux: use `apps/backend/.venv/bin/python` instead of `apps/backend/.venv/Scripts/python.exe`.

Environment files are created from the examples if you need to change defaults (all are git-ignored):

```powershell
copy .env.example .env
copy apps\backend\.env.example apps\backend\.env
copy apps\frontend\.env.example apps\frontend\.env   # set VITE_API_URL=http://localhost:8000
```

The frontend defaults to `http://localhost:8000` when `VITE_API_URL` is empty, so this step is only needed if you change the backend port.

## Run (two terminals)

**Terminal 1 — backend** (http://localhost:8000, Swagger at `/docs`):

```powershell
npm run start:backend:win
# or:  powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

> macOS/Linux: `npm run start:backend`

**Terminal 2 — frontend** (http://localhost:5173):

```powershell
npm run dev:frontend
```

## (Optional) Configure AI provider

The AI Workspace needs a provider. In the app: **Settings → AI Providers** → pick a provider, paste an API key (or select **Ollama** and run a local model), then **Test Connection** → **Save**. Keys are stored by the local backend and are never returned to the browser.

## Seed a demo repository (so you start with data)

With the backend running:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/seed-demo.ps1
# or a specific repo:
powershell -ExecutionPolicy Bypass -File scripts/seed-demo.ps1 -Url https://github.com/owner/repo
```

Pick a repo that follows a layered convention (folders like `api/`, `services/`, `models/`, `routes/`) so the architecture graph lights up all layers. PARTHA's own backend is a good, honest "we analyzed PARTHA with PARTHA" choice.

## 5-minute demo script

1. **Dashboard** — clean overview. "Point PARTHA at any repo."
2. **Upload → GitHub URL** — paste a repo, import. (Or use the pre-seeded one.)
3. **Repository → Overview** — real detected metadata: language, framework, entry point, files, config files.
4. **Architecture (the wow)** — interactive layered graph. Hover a node to highlight its dependencies, double-click to isolate a subtree, switch to **Request Flow**, toggle **Heatmap**, then **export a PNG**.
5. **Explorer → open a file** — browse the real tree and show **real file contents** in the editor.
6. **AI Workspace** — ask *"What are the main architectural boundaries?"* and *"What should I read first?"* → streamed, repo-grounded answer.
7. **Engineering Review** — close on the scorecard, findings, and roadmap. Export the report.

Avoid on stage: the Insights page (intentionally disabled) and the dependency stats that read zero (relationships/vulnerability scanning are on the roadmap).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `'.' is not recognized` / venv errors on Windows | Use the `:win` npm scripts or the `.ps1` helpers; the default scripts use Unix venv paths. |
| Frontend shows empty lists | Backend isn't running or is on a different port. Confirm http://localhost:8000/health returns `{"status":"ok"}`. |
| CORS errors in the browser console | Ensure `CORS_ORIGINS` (backend) includes `http://localhost:5173`. |
| AI Workspace errors | No provider configured — set one in Settings → AI Providers. |
| Port 8000 in use | Stop the other process, or run uvicorn with `--port 8001` and set `VITE_API_URL` accordingly. |
