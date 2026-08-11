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

## Navigation readiness and grouping

Top-level product routes and primary navigation are defined together in
`src/app/routes/productSurfaces.tsx`. A deferred surface must remain out of
primary navigation and record its delivery phase and blocking issues there.
Its direct route renders the shared unavailable-for-this-phase state; do not
restore a deferred page until its readiness gate changes.

That registry is also the single source of truth for **where** a surface
appears. Each entry carries a `navGroup`, and the sidebar renders groups in
registry order — it never hardcodes a route:

| `navGroup` | Contains | Rendering |
| --- | --- | --- |
| `flagship` | Dashboard, Repositories, Upload Repository | Top of the sidebar, unlabelled, full weight. |
| `analysis` | Architecture, Dependency Graph, Engineering Review, Insights, Documentation | Under a muted **Analysis** heading. Read-only evidence views. |
| `assist` | AI Workspace | Under a muted **Assist** heading, deliberately separate from `analysis`: an interactive tool over the same facts is not another view of record. |
| `utility` | Settings | Pinned to the footer above the account row, in its own `nav` landmark. |

Two rules the tests enforce, so changing them means changing a test on purpose:
reordering a surface in the registry reorders the sidebar, and every group
member stays a real focusable link — reducing emphasis never means hiding a
surface. A pinned surface still belongs to a navigation landmark; a link in a
bare `div` is invisible to landmark-based screen-reader navigation.

## Commands

Requires Node.js 22 (CI pins 22).

```bash
npm ci --prefix apps/frontend            # install from the lockfile

npm --prefix apps/frontend run dev       # dev server on http://localhost:5173
npm --prefix apps/frontend run lint      # eslint
npm --prefix apps/frontend run test      # vitest, with coverage
npm --prefix apps/frontend run test:watch
npm --prefix apps/frontend run build     # tsc -b && vite build
npm run generate:api-contract            # regenerate DTOs from FastAPI OpenAPI
npm --prefix apps/frontend run generate:api-contract -- --check # fail on drift
npm run test:prototype                   # disposable fixtures + Playwright journeys
```

The generated contract lives at
`src/shared/services/api/generated.ts` and must not be edited directly. The
generator imports backend module `app.main:app` from `apps/backend`, strips only import-time dynamic
datetime defaults, and runs the pinned `openapi-typescript@7.13.0` tool. The CI
API Contract Drift job installs both app lockfiles and runs the check command.

From the repository root: `npm run dev:frontend`, `npm run lint:frontend`,
`npm run build:frontend`, and `npm run test:prototype`. There is no root alias
for the Vitest suite — run `npm --prefix apps/frontend run test`.

Type errors surface in `build`, not `lint`. Run the build before opening a PR.

## Environment

`VITE_API_URL` sets the backend origin. It is **optional** — leave it unset for the default (`http://localhost:8000`). Copy `.env.example` to `.env` only if you need to point elsewhere. Vite inlines this at build time, so a change requires a restart.

## Backend

The app expects the PARTHA backend on `http://localhost:8000` (`npm run dev:backend` from the root). It requires an account: register through the UI, then sign in.

## Test coverage

Vitest covers shared infrastructure plus feature components, hooks, stores,
routing, repository switching, and architecture layout behavior. The prototype
acceptance runner creates disposable repositories, starts isolated backend and
frontend processes, and exercises the review-ready Architecture, Engineering
Review, and Insights journeys in Chromium. This executable acceptance coverage
is deliberately focused; it is not a claim of complete product coverage.
