# PARTHA Frontend

Vite + React frontend for PARTHA.

## Structure

```text
src/
  app/       App shell, router, pages, store, entrypoint
  features/  Domain features with colocated hooks/components
  shared/    Reusable components, hooks, services, types, utilities
  assets/    Static frontend assets
  styles/    Global styles
```

## Local Commands

```bash
npm --prefix apps/frontend run dev
npm --prefix apps/frontend run build
npm --prefix apps/frontend run lint
```
