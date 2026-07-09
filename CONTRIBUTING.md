# Contributing to PARTHA

Thanks for helping build PARTHA.

PARTHA is an Engineering Intelligence Platform. The central architectural rule is:

> Repository Intelligence is the source of truth. Product features consume it; they do not independently parse repositories.

This guide explains how to contribute safely, keep reviews focused, and preserve the system architecture as the project grows.

---

## Development Setup

### Prerequisites

| Tool | Version |
| --- | --- |
| Node.js | 22 or newer recommended |
| Python | 3.12 or 3.13 |
| Docker | Required for Compose validation |
| Git | Required for repository import workflows |

### Install

```bash
git clone https://github.com/Second-Origin/PARTHA.git
cd PARTHA

npm ci --prefix apps/frontend

cd apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
cd ../..
```

### Configure

```bash
cp .env.example .env
cp apps/frontend/.env.example apps/frontend/.env
cp apps/backend/.env.example apps/backend/.env
```

The local backend env example uses SQLite and local filesystem storage. Docker Compose injects PostgreSQL, Redis, and container storage settings separately.

### Run

```bash
npm run dev:backend
npm run dev:frontend
```

Useful endpoints:

- frontend: `http://localhost:5173`
- backend OpenAPI: `http://localhost:8000/docs`
- readiness: `http://localhost:8000/ready`
- metrics: `http://localhost:8000/metrics`

---

## Branch Strategy

| Branch | Purpose |
| --- | --- |
| `main` | Stable release snapshots. |
| `dev` | Active integration branch. |
| `feature/*` | New scoped feature work. |
| `fix/*` | Bug fixes. |
| `docs/*` | Documentation-only changes. |
| `chore/*` | Tooling, CI, maintenance, or repository hygiene. |

Rules:

- Do not push directly to `main`.
- Do not push directly to `dev`.
- Branch from the latest `dev`.
- Keep one branch focused on one issue or tightly related change.

```bash
git checkout dev
git pull origin dev
git checkout -b feature/repository-intelligence
```

---

## Issue Workflow

Before starting non-trivial work:

1. Check existing GitHub Issues.
2. Choose or create a focused issue.
3. Confirm the intended scope.
4. Wait for assignment or maintainer agreement when the change is large.
5. Keep implementation aligned with the issue.

Do not bundle unrelated cleanup into a feature PR. If you find an unrelated bug, open a separate issue.

---

## Pull Request Workflow

All PRs target `dev`.

Use the PR template and include:

- summary;
- related issue;
- changed files or systems;
- testing performed;
- risk and rollback notes;
- screenshots for UI changes;
- request/response examples for API changes;
- migration notes for persistence changes.

Use draft PRs for early architecture feedback.

Maintainers should be able to review the PR without reverse-engineering intent from the diff.

---

## Code Standards

### Repository Intelligence Boundary

Do:

- add reusable extraction to `apps/backend/app/intelligence/` when a feature needs repository facts;
- let feature services transform existing repository intelligence into response models;
- preserve one source of truth for architecture, dependencies, documentation, review, exports, and AI context.

Do not:

- re-read dependency manifests inside feature-specific services;
- traverse repository files in consumers when the intelligence engine should own the fact;
- let AI providers parse repositories directly;
- duplicate parser logic in frontend code.

### Backend

- Keep routes thin.
- Put business logic in services.
- Use schemas for request/response boundaries.
- Use typed service interfaces and explicit errors.
- Preserve standardized error responses.
- Avoid broad exception handling unless it adds operational context.
- Keep provider-specific AI logic inside provider implementations.
- Keep report builders separate from renderers.

### Frontend

- Keep app shell, feature code, and shared utilities separated.
- Reuse shared API clients and shared types.
- Avoid `any` unless there is a concrete interoperability reason.
- Preserve loading, empty, error, and success states.
- Keep UI changes scoped to the affected feature.

### General

- Remove dead code.
- Avoid speculative abstractions.
- Prefer small, reviewable changes.
- Do not commit secrets, local env files, local databases, build outputs, or generated caches.

---

## Testing Expectations

Run the checks relevant to your change.

### Frontend

```bash
npm run lint:frontend
npm run build:frontend
```

### Backend

```bash
npm run test:backend
```

### Full Build Gate

```bash
npm run build
```

### Docker / Platform Changes

If you change Docker, Compose, environment, CI, startup, health, readiness, or observability:

```bash
docker build -t partha-backend:local apps/backend
npm run docker:config
npm run docker:validate
```

If you cannot run a check locally, say so in the PR and explain why.

---

## Documentation Standards

Update documentation when a change affects:

- public behavior;
- setup or environment variables;
- API contracts;
- architecture boundaries;
- operational behavior;
- contributor workflows;
- product positioning.

Documentation should be:

- accurate to the current implementation;
- explicit about limitations;
- free of placeholder docs unless the section is intentionally a screenshot/demo placeholder;
- linked from `docs/README.md` when durable.

Use:

- `README.md` for public orientation;
- `docs/architecture/` for system boundaries and lifecycles;
- `docs/operations/` for deployment, release, dependency, and observability workflows;
- `docs/audit/` for evidence and audit trails;
- `docs/brand/` for visual identity guidance;
- `docs/product/` for product positioning and public-face audits.

---

## Commit Conventions

Use concise Conventional Commit-style messages:

```text
feat(repository): add safe file preview
fix(upload): report invalid archive errors
docs(readme): reposition public project overview
refactor(ai): isolate provider implementation
test(export): cover markdown renderer
chore(ci): validate compose readiness
```

Common types:

| Type | Use for |
| --- | --- |
| `feat` | User-facing or platform capability. |
| `fix` | Bug fix. |
| `refactor` | Internal change without intended behavior change. |
| `docs` | Documentation-only change. |
| `test` | Test additions or updates. |
| `chore` | Maintenance, tooling, CI, repository hygiene. |
| `security` | Security hardening or vulnerability fixes. |

---

## Review Expectations

Reviewers should check:

- issue scope;
- architecture boundaries;
- dependency direction;
- Repository Intelligence reuse;
- API compatibility;
- frontend/backend contract compatibility;
- error handling;
- security and secret handling;
- test coverage;
- documentation accuracy;
- operational impact.

For stale branches, compare against the latest `origin/dev` and call out duplicate or superseded work.

---

## Security and Secrets

Never commit:

- `.env` files;
- API keys;
- provider credentials;
- database credentials;
- local databases;
- uploaded repositories;
- generated caches or build artifacts.

If a secret is accidentally committed, notify maintainers immediately and rotate it. Removing it from a later commit is not enough.

---

## Need Help?

If the architecture is unclear, ask before implementing. PARTHA benefits more from a small, well-scoped design discussion than a large PR that has to be unwound.

Good contributor questions include:

- Should this fact belong in Repository Intelligence?
- Does this feature consume an existing model or need a new reusable extraction?
- Does this change affect API compatibility?
- Is this public behavior, internal architecture, or future roadmap?

Thanks for helping make PARTHA a trustworthy Engineering Intelligence Platform.
