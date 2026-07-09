# PARTHA — Path to Production & Team Working Structure

_A plan for taking PARTHA — the **Engineering Intelligence Platform** ("transform repositories into actionable engineering intelligence; understand systems, assess change impact, and make engineering decisions with confidence") — from a fast-moving MVP to a production-ready platform, and for structuring the work as the team grows from 2 to 5–7 experienced engineers._

Status as of Jul 9, 2026. Owners: Shaurya, Parth.

> **Update (this revision):** PARTHA has been repositioned from "AI-powered software architecture intelligence platform" to **"Engineering Intelligence Platform"**, with new brand assets (`docs/brand/VISUAL_IDENTITY.md`, hero/logo SVGs) and a `docs/product/PUBLIC_FACE_AUDIT.md`. A "production readiness baseline" has also merged into `dev` (PRs #30/#31). Importantly, that baseline is the **docs + observability scaffolding** layer — not the security hardening — so the P0 keystones below (E1 auth, E2 security) remain fully open. Shipped-vs-open status is now marked per epic in §3.

---

## 1. Where we are, where "production-ready" is

PARTHA today is a structurally complete MVP: import → parse → intelligence → product features works end to end. Backend is ~4.4k LOC of FastAPI, frontend ~8.3k LOC of React/TS, 66 backend tests, CI with lint/build/pytest/compose smoke, Alembic migrations, and an observability module already scaffolded.

The honest gap between "works in a demo" and "production-ready" is four things we do **not** have yet:

1. **No identity.** No users, no auth, no multi-tenancy. Every deploy is single-tenant and open. This is the single biggest blocker to real users.
2. **No security posture.** No rate limiting, no security headers, CORS not locked down, AI provider secrets not encrypted at rest, no dependency/secret scanning gate.
3. **Intelligence is still heuristic.** The persisted knowledge graph — the thing the whole architecture is designed around — is still "in progress." Architecture/dependency/review/docs are all self-labeled "Partial."
4. **Thin reliability & test safety net.** Frontend has **zero** tests. No error tracking, no SLOs, no staging environment, no rollback story beyond "redeploy."

"Production-ready" for PARTHA = a user can sign in, import their repo, trust the output, and we can operate it safely (observe it, roll it back, keep their data and secrets safe). Everything below serves that definition.

> **Housekeeping — `main` is stale, `dev` is the real trunk.** As of this revision, `dev` sits ~18 commits and 158 files ahead of `main` (the production-readiness baseline, AI providers, reports/export, intelligence engine, and ops docs all live on `dev`). The earlier "whole tree modified" mess is resolved on the remote — it landed cleanly via PRs #30/#31; any local churn is CRLF/filemode noise from the mount. The real risk now: **anyone cloning `main` gets almost none of the platform.** Before onboarding, either promote `dev` → `main` on a regular cadence or make `dev` the default branch (see §2.2/§2.5). Also: **issue creation is currently restricted on the repo** — lift that (or pre-create the issues yourselves) before contributors arrive.

---

## 2. Team working structure

You already have a strong `CONTRIBUTING.md` (dev/main/feature branches, Conventional Commits, squash merge, issue-assignment flow, PR template). Keep all of it. The additions below are what a 5–7 person team needs that a 2-person team can skip.

### 2.1 Plan in a hierarchy, track in one board

Adopt GitHub's now-GA **issue types + sub-issues** instead of the `[AI 1]` / `[AI 1.3]` naming convention. It gives you the same hierarchy natively, and sub-issues inherit the parent's Project and Milestone automatically.

```
Epic  (issue type: Epic)      e.g. "Authentication & Multi-Tenancy"
 └─ Feature (issue type: Feature)   "Email/password + session auth"
     └─ Task (issue type: Task)     "Add User model + Alembic migration"
     └─ Task                        "Add JWT issue/verify + refresh rotation"
 └─ Bug   (issue type: Bug)
```

Run **one GitHub Project (v2)** for the whole team with these views:
- **Board** (Todo / In Progress / In Review / Done) — daily driver.
- **Table** grouped by Milestone — release planning.
- **Roadmap** — the timeline for stakeholders / new contributors.

Custom fields to add to the Project: `Priority` (P0–P3, you already use this), `Area`, `Estimate` (S/M/L), `Sprint`.

### 2.2 Milestones = releases

Move from continuous merging to **milestone-based delivery** so a growing team pulls in the same direction. Proposed milestones (details in §3):

| Milestone | Theme | Definition of "shipped" |
| --- | --- | --- |
| `M1 — Foundations` | Auth, security baseline, clean repo, frontend test harness | A user can sign in; the app is not open to the internet |
| `M2 — Real Intelligence` | Persisted knowledge graph, dependency edges, evidence-backed review | Outputs are trustworthy, not heuristic guesses |
| `M3 — Operate It` | Observability, error tracking, staging, deploy + rollback | We can run it safely and see when it breaks |
| `M4 — Launch Polish` | Finish "Partial" features, AI workspace epic, E2E coverage | End-to-end story is demo-perfect and covered by tests |

Timebox each to ~3–4 weeks. Don't start M2 area-work before M1's auth boundary exists — features built without auth get re-plumbed later.

### 2.3 Labels (consolidated taxonomy)

Keep it small and orthogonal. One label per axis:

- **Area:** `area/backend` `area/frontend` `area/ai` `area/infra` `area/db` `area/docs`
- **Type:** use native issue types (Epic/Feature/Task/Bug) instead of type labels.
- **Priority:** `P0`–`P3` (already in your template).
- **Status/flow:** `blocked` `needs-design` `ready` (`ready` = spec'd, assignable).
- **Contributor-facing** (for when the 3–5 arrive): `good-first-issue` `help-wanted`.

### 2.4 Ownership as you scale

Add a `CODEOWNERS` file so PRs auto-request the right reviewer. Assign areas to people, not everything to you two:

```
# .github/CODEOWNERS
/apps/backend/app/ai/            @ai-owner
/apps/backend/app/parsers/       @intelligence-owner
/apps/backend/app/graph/         @intelligence-owner
/apps/frontend/                  @frontend-owner
/apps/backend/app/core/          @shaurya @parth   # infra/config stays with founders
/.github/ @shaurya @parth
```

Rule of thumb for experienced hires: give each new person **one Area to own** (they become the default reviewer and decision-maker there), not a stream of disconnected tickets. Ownership scales; task-assignment doesn't.

### 2.5 Branch protection & required checks

Now that non-founders will push, enforce in GitHub settings what `CONTRIBUTING.md` currently only asks politely:
- Protect `main` and `dev`: no direct pushes, require PR.
- Require the `Frontend`, `Backend`, and `Docker Compose` CI jobs to pass before merge.
- Require **1 approving review** (2 for anything touching `core/`, auth, or migrations).
- Require branches up to date with `dev` before merge; require linear history (you already squash).
- Add **Dependabot** + **CodeQL** (or GitHub Advanced Security) as required status checks — this is part of the security baseline anyway.

### 2.6 Definition of Ready / Definition of Done

Put these in the repo (e.g. `docs/planning/DEFINITION_OF_DONE.md`) and gate on them.

**Definition of Ready** (before an issue is assignable / labeled `ready`):
- Clear acceptance criteria; area + priority + milestone set; dependencies linked; design agreed if it touches API/persistence/security.

**Definition of Done** (before a PR merges):
- Acceptance criteria met; tests added/updated and CI green; no new `any` / broad excepts; docs updated if behavior changed; no secrets/build artifacts committed; feature reachable through the UI or documented as internal.

### 2.7 Cadence & communication

- **Weekly planning** (30–45 min): triage new issues → `ready`, pull the next slice into the sprint, confirm milestone burn-down.
- **Async standups** in the Project (or a `#standup` channel): what moved, what's blocked. No daily meeting needed for experienced devs.
- **PR SLA:** first review within one working day; keep PRs < ~400 lines of diff — split epics into task-sized PRs.
- Keep all design discussion **on the issue**, per your existing philosophy, so new contributors can read the decision trail.

---

## 3. Production-readiness roadmap (the epics)

These are the "solid new issues" to create, grouped by milestone. Each is an **Epic**; the ready-to-paste child issues are in §4. PARTHA's existing open AI epic (#14 and its 1.3–1.8 subtasks) folds into **M4**.

**Status legend:** 🔴 not started · 🟡 partially shipped · 🟢 done.

### M1 — Foundations
- 🔴 **E1. Authentication & Multi-Tenancy** — user model, sign-up/sign-in, sessions/JWT with refresh rotation, per-user data scoping. _The keystone; almost everything else assumes it._ **Confirmed absent on `dev` — no auth/user modules exist yet.**
- 🔴 **E2. Security Baseline** — rate limiting (slowapi + Redis), security-headers middleware, CORS lockdown, encrypted-at-rest storage for AI provider keys, Dependabot + CodeQL + secret scanning in CI. **Not started; the "readiness baseline" that shipped did not include any of this.**
- 🟡 **E3. Repo Hygiene & Frontend Test Harness** — build-artifact hygiene is **done** on `dev` (stopped tracking `dist/`/`tsbuildinfo`, improved monorepo `.gitignore`). **Still open:** promote `dev`→`main` cadence, and the frontend test harness (Vitest + RTL) — frontend still has zero tests.

### M2 — Real Intelligence
- 🔴 **E4. Persisted Knowledge Graph** — the core in-progress work: a real graph model (nodes/edges/artifacts) persisted in Postgres, replacing per-feature heuristics as the single source of truth. _An `intelligence/engine.py` exists but outputs are still heuristic/in-memory — the persisted graph is not built yet._
- 🔴 **E5. Dependency Graph Depth** — resolve real edges between manifests, add outdated + vulnerability signals, surface a true dependency graph (not just an inventory).
- 🔴 **E6. Evidence-Backed Engineering Review** — expand rule depth and make every finding cite concrete files/lines from the graph. _(A `test_review_evidence.py` now exists — evidence scaffolding is beginning.)_

### M3 — Operate It  _(partially underway via the readiness baseline)_
- 🟡 **E7. Observability & Error Tracking** — `apps/backend/app/core/observability.py` and `docs/operations/observability.md` have **shipped** (scaffolding). **Still open:** wire it to real metrics + traces (OpenTelemetry), add error tracking (Sentry), and define 2–3 user-facing SLOs + burn-rate alerts.
- 🟡 **E8. Deploy Pipeline & Environments** — a `.github/workflows/release.yml`, `docs/operations/production-deployment.md`, and `release-management.md` have **shipped**, and Compose already uses Postgres. **Still open:** an actual staging environment, container registry, automated deploy, verified rollback, and DB backups.
- 🔴 **E9. Background Work Robustness** — make ingestion of large repos async and resilient (timeouts, retries, idempotency, progress) so the API stays responsive.

### M4 — Launch Polish
- **E10. AI Workspace Completion** — absorb existing issues #14, #32–#37 (provider config/secrets, context retrieval, streaming, persistence, citations, hardening).
- **E11. Finish the "Partial" Surfaces** — Insights backend endpoint, real Settings/account, deep-link search, documentation HTML/export quality.
- **E12. End-to-End Test Coverage** — Playwright E2E for the golden path (import → explore → review → AI), plus API contract tests.

---

## 4. Ready-to-paste issues

Formatted for your `engineering_task.yml` template (Task / Rationale / References / Implementation Notes / Acceptance Criteria / Priority). Create the Epics first, then attach the Tasks as **sub-issues**. This is a starter set for **M1 + the start of M2** — the highest-leverage work. Repeat the pattern for later milestones.

---

### EPIC E1 — Authentication & Multi-Tenancy
**Type:** Epic · **Area:** backend, frontend, db · **Priority:** P0 · **Milestone:** M1

**Goal.** Introduce identity so PARTHA can support real, isolated users. Every repository, analysis, and provider secret becomes owned by a user (or workspace). No feature should read or write data outside the current user's scope.

**Why now.** The platform is currently open and single-tenant. Auth is a prerequisite for security hardening (E2), per-user provider keys, conversation persistence (#35), and any real deployment. Building more features before this means re-plumbing every table and route later.

**Child issues:** E1.1–E1.5 below.

> Optional accelerator: the workspace has the Auth0 skill set installed (`auth0-fastapi-api`, `auth0-react`). If you'd rather not own auth infrastructure, Auth0 can provide login + JWT issuance and we only validate tokens + scope data. Decide build-vs-buy in this epic before starting E1.2.

---

#### E1.1 — Add User model and auth tables + migration
**Type:** Task · **Area:** backend, db · **Priority:** P0

**Task.** Add `User` (and, if we choose workspaces, `Workspace` / `Membership`) SQLAlchemy models and an Alembic migration. Add `owner_id` foreign keys to `Repository` and any other user-scoped tables.

**Rationale.** Everything in this epic depends on a persisted identity and an ownership column to scope queries by.

**References.** `apps/backend/app/models/`, `apps/backend/alembic/versions/`, `apps/backend/app/repositories/`.

**Implementation Notes.** Use UUID primary keys for users. Hash passwords with `argon2` or `bcrypt` (never store plaintext). Decide single-user-ownership vs. workspaces up front — changing later is a painful migration. Backfill existing rows to a system/seed user.

**Acceptance Criteria.**
- `User` model + migration merged; `upgrade`/`downgrade` both run clean.
- `Repository` (and other user data) carry an `owner_id` FK.
- Repository queries filter by owner; a repo request test proves cross-user access returns 404/403.
- Tests added; CI green.

---

#### E1.2 — Implement JWT issue/verify with refresh-token rotation
**Type:** Task · **Area:** backend · **Priority:** P0

**Task.** Add auth endpoints (`/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`) issuing short-lived access tokens and rotating refresh tokens. Add a `get_current_user` dependency.

**Rationale.** Provides the session mechanism the frontend and all protected routes need.

**References.** `apps/backend/app/api/routes/`, `apps/backend/app/api/deps.py`, `apps/backend/app/core/config.py`.

**Implementation Notes.** Short access-token TTL (~15 min) + rotating refresh token stored hashed and revocable. Sign with a secret from config/env (never hardcoded). Consider httpOnly cookies for the web client to avoid XSS token theft. If we chose Auth0 in E1, this task becomes "validate Auth0 JWTs + map to local user" instead.

**Acceptance Criteria.**
- Register/login/refresh/logout work end to end with tests.
- `get_current_user` rejects missing/expired/invalid tokens with 401.
- Refresh rotation invalidates the used refresh token; reuse is detected and rejected.
- No secrets committed; CI green.

---

#### E1.3 — Protect existing routes and scope data to the current user
**Type:** Task · **Area:** backend · **Priority:** P0

**Task.** Require authentication on all repository/analysis/ai/documentation/reports routes and filter every query by `owner_id`.

**Rationale.** Auth is worthless if existing endpoints still serve everyone's data.

**References.** `apps/backend/app/api/routes/*.py`, `apps/backend/app/services/*.py`.

**Implementation Notes.** Add the `get_current_user` dependency at the router level where possible. Push ownership filtering into the repository/service layer, not individual handlers, so it can't be forgotten. Return 404 (not 403) for other users' resources to avoid leaking existence.

**Acceptance Criteria.**
- All non-public routes return 401 without a valid token.
- Tests prove user A cannot read/mutate user B's repositories, analyses, docs, or reports.
- CI green.

---

#### E1.4 — Frontend auth flow (login/register, token handling, guarded routes)
**Type:** Task · **Area:** frontend · **Priority:** P0

**Task.** Add login/register pages, token/session handling in the API client, an auth store, and route guards that redirect unauthenticated users.

**Rationale.** Users need a way to actually sign in; protected pages must not render for anonymous users.

**References.** `apps/frontend/src/app/routes/router.tsx`, `apps/frontend/src/app/store/useAppStore.ts`, `apps/frontend/src/shared/services/api/client.ts`.

**Implementation Notes.** Centralize auth in the API client (attach token, refresh on 401, redirect on refresh failure). Prefer httpOnly cookies if E1.2 uses them. Wire the existing Settings "account" placeholders to real user data.

**Acceptance Criteria.**
- Unauthenticated users are redirected to login from guarded routes.
- Login persists a session across refresh; logout clears it.
- 401 triggers a silent refresh, then redirect if that fails.
- A component/integration test covers the guard.

---

#### E1.5 — Encrypt and store AI provider keys per user
**Type:** Task · **Area:** backend, ai · **Priority:** P1

**Task.** Persist each user's AI provider API keys encrypted at rest and inject them per-request instead of relying on a single global env key.

**Rationale.** Multi-tenant AI requires per-user keys; storing them in plaintext or sharing one global key is a security and billing problem. Directly unblocks AI epic #32 (Provider Configuration & Secret Management).

**References.** `apps/backend/app/ai/providers/`, `apps/backend/app/core/config.py`, issue #32.

**Implementation Notes.** Encrypt with a KMS or a Fernet key sourced from env; never return keys in API responses (write-only field, show last-4 only). Scope key lookup by `owner_id`.

**Acceptance Criteria.**
- Provider keys are stored encrypted and never serialized back to the client in full.
- AI requests use the current user's key; missing key returns a clear, actionable error.
- Tests cover encrypt/decrypt round-trip and the no-leak contract; CI green.

---

### EPIC E2 — Security Baseline
**Type:** Epic · **Area:** backend, infra · **Priority:** P0 · **Milestone:** M1

**Goal.** Establish the minimum security posture before exposing PARTHA to real traffic: rate limiting, security headers, locked-down CORS, and automated dependency/secret scanning.

**Why now.** "Security is one of the fastest ways to lose production trust." These are cheap to add now and expensive to retrofit after an incident.

**Child issues:** E2.1–E2.3.

---

#### E2.1 — Add rate limiting (Redis-backed)
**Type:** Task · **Area:** backend, infra · **Priority:** P0

**Task.** Add per-IP and per-user rate limiting, with tighter budgets on expensive routes (ingestion, AI).

**Rationale.** Prevents abuse and runaway AI cost; a baseline production requirement.

**References.** `apps/backend/app/main.py`, `apps/backend/app/core/redis.py` (Redis already present).

**Implementation Notes.** `slowapi` (or an ASGI middleware) backed by the existing Redis. Sensible defaults globally, stricter on `/analyze`, `/ai`, and archive upload. Return `429` with `Retry-After`.

**Acceptance Criteria.**
- Exceeding the limit returns 429 with `Retry-After`; a test proves it.
- AI and ingestion endpoints have stricter, separately-configured budgets.
- Limits are configurable via env; CI green.

---

#### E2.2 — Security headers + CORS lockdown
**Type:** Task · **Area:** backend · **Priority:** P1

**Task.** Add a security-headers middleware and replace permissive CORS with an explicit allowlist from config.

**Rationale.** Missing headers and open CORS are common, easily-scanned production failures.

**References.** `apps/backend/app/main.py`, `apps/backend/app/core/config.py`.

**Implementation Notes.** Set `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`, and `Strict-Transport-Security`. CORS origins come from an env allowlist; no `*` with credentials.

**Acceptance Criteria.**
- Responses carry the security headers (asserted in a test).
- CORS rejects unlisted origins; allowed origins come from config.
- CI green.

---

#### E2.3 — Dependency, secret, and code scanning in CI
**Type:** Task · **Area:** infra · **Priority:** P1

**Task.** Enable Dependabot, CodeQL, and secret scanning; make them required checks on `main`/`dev`.

**Rationale.** Automated supply-chain and secret detection is table stakes and part of the merge gate.

**References.** `.github/workflows/ci.yml`, `.github/` config.

**Implementation Notes.** Add `dependabot.yml` for npm + pip. Add a CodeQL workflow for JS/TS + Python. Enable push-protection secret scanning in repo settings. Triage the initial findings backlog as follow-up issues.

**Acceptance Criteria.**
- Dependabot opens update PRs; CodeQL runs on PRs; secret scanning is on.
- These checks are required before merge (branch protection).
- Initial critical/high findings are triaged into issues.

---

### EPIC E3 — Repo Hygiene & Frontend Test Harness
**Type:** Epic · **Area:** frontend, infra · **Priority:** P1 · **Milestone:** M1

**Goal.** Make `main` clean and trustworthy for new contributors, and stand up the missing frontend test capability.

**Why now.** The frontend has zero tests and the working tree/build artifacts are messy. Both undermine confidence exactly when new people join.

**Child issues:** E3.1–E3.2.

---

#### E3.1 — Establish `dev`→`main` release cadence + green fresh clone
**Type:** Task · **Area:** infra · **Priority:** P1 · _(build-artifact hygiene already done on `dev`)_

**Task.** `dist/`/`tsbuildinfo` are no longer tracked and the monorepo `.gitignore` is improved — that part is **done**. Remaining work: fix that `main` is ~158 files behind `dev`, and verify a fresh clone of the trunk builds and tests green with documented steps.

**Rationale.** New contributors judge a project by whether the default branch runs on day one. Right now cloning `main` gets almost none of the platform.

**References.** `.gitignore`, `README.md` Getting Started, `.github/workflows/release.yml`.

**Implementation Notes.** Decide: either make `dev` the default branch, or open a `dev`→`main` promotion PR now and repeat it every milestone. Then confirm README setup steps work from a clean clone on a fresh machine/container.

**Acceptance Criteria.**
- Default/trunk branch reflects the current platform (no large unexplained gap between it and `dev`).
- A documented `dev`→`main` promotion ritual exists (or `dev` is the default branch).
- Fresh clone → documented setup → frontend build + backend tests pass.

---

#### E3.2 — Stand up Vitest + React Testing Library with coverage gate
**Type:** Task · **Area:** frontend · **Priority:** P1

**Task.** Add Vitest + RTL, write first real tests (an API client behavior + a guarded route or a core hook), and add the frontend test job to CI with a coverage floor.

**Rationale.** The frontend currently has no safety net; as more people touch it, regressions will ship silently.

**References.** `apps/frontend/`, `.github/workflows/ci.yml`.

**Implementation Notes.** Start the coverage floor low (e.g. 20%) and ratchet up per milestone. Prioritize testing the API client, auth guard, and feature hooks over presentational components.

**Acceptance Criteria.**
- `npm --prefix apps/frontend run test` runs in CI and is required.
- At least 3 meaningful tests exist (client/hook/guard).
- Coverage threshold enforced and documented.

---

### EPIC E4 — Persisted Knowledge Graph  _(M2 — start of "real intelligence")_
**Type:** Epic · **Area:** backend, db, ai · **Priority:** P0 · **Milestone:** M2

**Goal.** Deliver the persisted knowledge graph that `CONTRIBUTING.md` and the README describe as the single source of truth — a real model of nodes (modules, files, services), edges (imports, calls, dependencies), and artifacts, persisted and queryable, that architecture/dependency/review/docs/AI/search all read from.

**Why now.** It's the core in-progress item and the reason the current outputs are "heuristic." Every "Partial" feature upgrades to "reliable" once it reads from a shared graph instead of re-deriving structure. This is what actually takes PARTHA to the next level technically — do it right after the M1 auth/security boundary exists so the graph is user-scoped from day one.

**Suggested child issues.** (spec these in the epic before starting)
- E4.1 Define the graph schema + persistence (Postgres tables or a graph store) and migration.
- E4.2 Populate the graph from the existing parser/intelligence engine during ingestion.
- E4.3 Migrate the architecture view to read modules/edges from the graph.
- E4.4 Migrate engineering review to cite graph-backed evidence (feeds E6 and issue #36 citations).
- E4.5 Expose a graph query API the AI context retrieval (#33) consumes.

**Acceptance Criteria (epic-level).**
- A persisted, user-scoped graph is produced on ingestion and survives restarts.
- At least two product surfaces (architecture + review) read from the graph rather than recomputing.
- Documented schema + query API; tests cover graph build and a cross-feature read.

---

## 5. Suggested first two weeks

1. **Day 1–2:** E3.1 (fix `main`↔`dev`: promote or switch default) + set up branch protection, CODEOWNERS, the Project board, issue types, and milestones. Lift the issue-creation restriction. Onboarding surface ready before anyone joins.
2. **Decide build-vs-buy on auth** (E1 note) — this unblocks the whole M1 critical path.
3. **Parallelize M1:** one owner on E1 (auth), one on E2 (security), a new hire on E3.2 (frontend tests) as a scoped, self-contained on-ramp.
4. Only after the auth boundary lands, open E4 (knowledge graph) design discussion on its epic issue.

_Progress already banked (don't re-scope): build-artifact hygiene, observability + deployment/release **docs and scaffolding**, the AI provider architecture, and reports/export. The gap to production is the security boundary (E1/E2) and turning the shipped ops scaffolding into live metrics/alerts/staging (E7/E8)._

---

## Sources

- [Evolving GitHub Issues and Projects (GA)](https://github.blog/changelog/2025-04-09-evolving-github-issues-and-projects/) · [Adding sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues) · [Best practices for Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/best-practices-for-projects)
- [A Practical Guide to FastAPI Security](https://davidmuraya.com/blog/fastapi-security-guide/) · [FastAPI production deployment best practices (Render)](https://render.com/articles/fastapi-production-deployment-best-practices) · [API Security Best Practices for Production (OneUptime)](https://oneuptime.com/blog/post/2026-02-20-api-security-best-practices/view)
- [Production Readiness Checklist for Web Applications — 2026 (Rootcode)](https://www.rootcode.in/blog/production-readiness-checklist-for-web-applications-the-2026-guide-mr33mw4l) · [Production readiness checklist (getDX)](https://getdx.com/blog/production-readiness-checklist/) · [The Ultimate SRE Reliability Checklist (OneUptime)](https://oneuptime.com/blog/post/2025-09-10-sre-checklist/view)
- Internal: `README.md`, `CONTRIBUTING.md`, `docs/audit/`, repository issues #14, #32–#37.
