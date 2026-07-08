# PARTHA

PARTHA is a repository intelligence product with a Vite frontend and FastAPI backend organized as a production-ready monorepo.

## Repository Structure

```text
apps/
  frontend/   Vite + React application
  backend/    FastAPI application, Alembic migrations, tests, Dockerfile
docs/         Product and engineering documentation
packages/     Shared packages reserved for future cross-app code
scripts/      Local development and verification helpers
```

## Local Development

Install frontend dependencies from `apps/frontend` or use the existing root `node_modules` during local migration.

```bash
npm run dev:frontend
npm run dev:backend
```

The frontend runs on `http://localhost:5173` and the backend on `http://localhost:8000`.

## Verification

```bash
npm run build:frontend
npm run test:backend
npm run docker:config
```

## Docker

```bash
npm run docker:up
```

Docker Compose builds the API from `apps/backend` and runs PostgreSQL and Redis for backend development.
