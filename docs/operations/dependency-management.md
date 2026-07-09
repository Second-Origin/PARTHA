# Dependency Management

This document defines the dependency maintenance baseline for PARTHA.

## Policy

- Keep dependency updates reviewable and separate from feature work.
- Prefer patch/minor updates unless a major update has a migration plan.
- Do not commit generated dependency output unless it is the package manager lockfile or required project metadata.
- Treat security advisories as engineering work, not drive-by cleanup.

## Frontend

The frontend uses npm with `apps/frontend/package-lock.json`.

Routine checks:

```bash
npm ci --prefix apps/frontend
npm --prefix apps/frontend run lint
npm --prefix apps/frontend run build
npm audit --prefix apps/frontend
```

When updating dependencies:

```bash
npm --prefix apps/frontend update
```

Review lockfile changes before committing.

## Backend

The backend dependencies are declared in `apps/backend/pyproject.toml`.

Routine checks:

```bash
cd apps/backend
python -m pip install -e .
python -m pytest
python -m pip list --outdated
```

When adding a backend dependency, keep it narrowly scoped and document why the standard library or existing dependencies are insufficient.

## Security Updates

For security updates:

1. Identify the affected package and vulnerable versions.
2. Confirm whether the vulnerable code path is used.
3. Update the dependency.
4. Run relevant frontend/backend validation.
5. Include advisory links and risk notes in the PR.
