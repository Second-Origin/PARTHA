# PARTHA Frontend

Vite + React + TypeScript frontend for PARTHA.

This app lives at `apps/frontend` in the PARTHA monorepo. For contributor workflow and engineering rules, see the root [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Structure

```text
src/
  app/       Shell, router, pages, stores, entrypoint
  features/  Domain features with colocated hooks, components, and tests
  shared/    API clients, reusable UI, config, hooks, types, utilities
  styles/    Global styles and design tokens
  test/      Vitest setup
```

Every application route is behind the `RequireAuth` guard; only `/login` and `/register` are public. All backend calls go through the shared API client in `src/shared/services/api/`, which owns access-token attachment and 401 handling — do not call `fetch` directly from a feature.

## Navigation readiness

Top-level product routes and primary navigation are defined together in
`src/app/routes/productSurfaces.tsx`. A deferred surface must remain out of
primary navigation and record its delivery phase and blocking issues there.
Its direct route renders the shared unavailable-for-this-phase state; do not
restore a deferred page until its readiness gate changes.

## Commands

Requires Node.js 22 (CI pins 22).

```bash
npm ci --prefix apps/frontend            # install from the lockfile

npm --prefix apps/frontend run dev       # dev server on http://localhost:5173
npm --prefix apps/frontend run lint      # eslint
npm --prefix apps/frontend run test      # vitest, with coverage
npm --prefix apps/frontend run test:watch
npm --prefix apps/frontend run build     # tsc -b && vite build
```

From the repository root: `npm run dev:frontend`, `npm run lint:frontend`, `npm run build:frontend`. There is no root alias for the frontend tests — run `npm --prefix apps/frontend run test`.

Type errors surface in `build`, not `lint`. Run the build before opening a PR.

## Environment

`VITE_API_URL` sets the backend origin. It is **optional** — leave it unset for the default (`http://localhost:8000`). Copy `.env.example` to `.env` only if you need to point elsewhere. Vite inlines this at build time, so a change requires a restart.

## Backend

The app expects the PARTHA backend on `http://localhost:8000` (`npm run dev:backend` from the root). It requires an account: register through the UI, then sign in.

## Test coverage

The suite currently covers the auth store, API client, error mapping, route guard, and a few utilities. Feature and page coverage is thin and there is no end-to-end suite. New frontend behaviour should come with tests; this is an area where contributions are especially welcome.
