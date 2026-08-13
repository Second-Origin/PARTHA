# Contributing to PARTHA

These are the project rules, not a welcome page. If you follow them, your pull request can be reviewed and merged. If you do not, it will be sent back regardless of the quality of the code.

PARTHA is a Repository Intelligence Platform. One architectural rule sits above all others:

> **Repository Intelligence is the shared repository-understanding layer. Architecture, dependencies, reviews, documentation, exports, and optional AI features consume it. AI must remain a downstream consumer, never an independent interpreter of the repository.**

Throughout this document, **must** and **must not** are requirements, **should** is a strong expectation, and **may** is permission.

## 0. Strategy alignment (merge gate)

PARTHA's direction is set by a single source of truth: the roadmap document
`PARTHA_Market_Fit_Product_Roadmap.html` (the local strategy file;
ask the maintainer if you cannot see it). It defines the capability sequencing,
gates, rejected paths (§27), and market-fit exit criteria (§28).

A pull request is **in scope only if it advances one of the §23 workstreams
toward a §28 market-fit exit criterion, with accepted evidence.** A "quick
useful surface" or breadth addition that does not move a §28 criterion is
**out of scope** and should not be proposed or merged. The encouraged default
is to *deepen the existing moat* (versioned evidence, history and drift,
governed team memory, workflow outcomes); new surfaces or languages are the
discouraged direction and need explicit owner justification.

You must fill the **Roadmap alignment** section of the pull request template
on every pull request — naming the §23 workstream, the §28 criterion, and the
accepted evidence. A pull request that cannot fill it is, by definition, out
of scope and will be sent back.

Editing the roadmap itself is a strategy-sensitive change reserved to the
maintainer; do not treat roadmap content as something you may revise.

---

## 1. Setup

### Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Python | 3.12 or 3.13 | Backend |
| Node.js | 22 | Frontend |
| Git | any recent | Everything |

### Backend

```bash
cd apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
cd ../..

npm run dev:backend
```

The backend defaults to SQLite and local filesystem storage, so it starts with no PostgreSQL and no Redis. No `.env` file is required for local development — every setting has a working default. Copy `apps/backend/.env.example` only to change one.

### Frontend

```bash
npm ci --prefix apps/frontend
npm run dev:frontend
```

Register an account through the UI, then sign in.

### Where the code lives

| Path | Contents |
| --- | --- |
| `apps/backend/app/intelligence/` | **Repository Intelligence engine and models.** The system's core boundary. |
| `apps/backend/app/api/` | Routes and dependency wiring |
| `apps/backend/app/services/` | Application services |
| `apps/backend/app/analysis/`, `graph/`, `review/`, `ai/`, `reports/` | Consumers of Repository Intelligence |
| `apps/backend/app/auth/`, `core/`, `models/`, `storage/` | Auth, config, ORM models, local storage |
| `apps/backend/alembic/`, `apps/backend/tests/` | Migrations, backend tests |
| `apps/frontend/src/` | `app/` shell and routes, `features/`, `shared/` |
| `docs/` | Public documentation |

---

## 2. Fork-first workflow

PARTHA uses a **fork-first** contribution model. You do not get push access to the official repository.

**Contributors do not push directly to `dev`. They push a dedicated working branch to their own fork and open a pull request targeting `dev`.**

All normal development pull requests target `dev`. The `main` branch is reserved for maintainer-controlled releases or promotion from `dev`.

### Set up your fork once

1. Fork `Second-Origin/PARTHA` on GitHub.
2. Clone your fork and add the official repository as `upstream`:

```bash
git clone https://github.com/<your-username>/PARTHA.git
cd PARTHA
git remote add upstream https://github.com/Second-Origin/PARTHA.git
git remote -v
```

### For every piece of work

```bash
git fetch upstream
git checkout -b feature/123-short-description upstream/dev
# ...commit your work...
git push -u origin feature/123-short-description
```

Then open a pull request from your fork's branch to `Second-Origin/PARTHA:dev`.

### You must not

- push directly to `dev`
- push directly to `main`
- develop directly on your fork's `dev` branch
- open ordinary feature or fix pull requests against `main`
- combine unrelated issues in one branch
- reuse a merged branch for new work
- self-merge your pull request
- rewrite or force-push another contributor's branch

---

## 3. Claim an issue before you start

Substantial work **must** be claimed first. Unclaimed work may be closed unmerged even if it is correct, because it may duplicate or conflict with work already in progress.

Before starting, you must:

1. Read the complete issue.
2. Read its comments, linked issues, dependencies, and acceptance criteria.
3. Confirm it is open and not already assigned to someone else.
4. Comment on the issue stating **why** you want to work on it and requesting to be assigned.
5. Start working — you do **not** need to wait for a maintainer to acknowledge before you begin. The comment itself is the claim; the maintainer will assign you on GitHub when able.
6. Ask for clarification if the acceptance criteria are not testable, **before** you implement anything.

If you cannot assign yourself because of GitHub permissions, your comment is the claim mechanism — post it, then begin.

You must not begin substantial work on an issue that is already assigned to someone else. If one is, pick a different issue.

You must not begin substantial work on:

- an obsolete issue
- an issue whose scope is disputed
- an issue blocked by unmerged prerequisite work
- an issue without testable acceptance criteria

If no suitable issue exists, propose one using an existing issue template before implementing. Do not open a duplicate issue — search first, and comment on the existing one instead.

### Choosing a template

The repository provides three issue templates in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/):

| Template | Use it for |
| --- | --- |
| **Bug Report** | Broken or incorrect behaviour. Give exact reproduction steps (route, endpoint, input repository, commands), the expected behaviour, the actual behaviour, evidence such as logs or payloads, and your environment. |
| **Feature Request** | A new capability or user workflow. State the problem first, then the proposed behaviour, the affected pages/endpoints/services, testable acceptance criteria, and any risks or dependencies. |
| **Engineering Task** | Technical debt, refactors, tests, infrastructure. State the task, why it matters now, the likely files and constraints, and acceptance criteria. |

In every template: write acceptance criteria that someone other than you can verify, name the affected components, and disclose dependencies and blocking work.

For documentation changes, open a Feature Request or Engineering Task describing what is inaccurate and what it should say.

### Security vulnerabilities

**Security vulnerabilities must never be filed as public issues.** Report them privately through [SECURITY.md](SECURITY.md). Do not include a vulnerability, an exploit, or a proof of concept in an issue, a pull request, or a comment.

---

## 4. Branch naming

Every issue gets a dedicated branch created from the latest `upstream/dev`.

```text
<type>/<issue-number>-<short-description>
```

```text
feature/123-python-symbol-extraction
fix/145-owner-scope-analysis
docs/152-contribution-workflow
test/167-archive-regression
refactor/181-parser-boundary
security/193-provider-configuration
chore/204-ci-cache
```

Allowed types: `feature`, `fix`, `docs`, `test`, `refactor`, `chore`, `security`.

One branch normally addresses one issue. If an issue is too large for a single reviewable pull request, split the issue, or use explicitly linked dependent pull requests (§9).

---

## 5. Rebase onto `dev`

You must rebase onto the latest `upstream/dev` **before opening** a pull request, and **again before final review**.

```bash
git fetch upstream
git rebase upstream/dev
git push --force-with-lease origin <branch-name>
```

Rules:

- Resolve conflicts locally, and rerun the relevant validation afterwards. A rebase can silently break code that previously passed.
- Use `--force-with-lease`. Never use unrestricted `--force`.
- Do not merge `dev` into your working branch merely to avoid rebasing, unless a maintainer explicitly asks you to.
- Never rebase or force-push a branch owned by someone else.

---

## 6. Pull requests

When the issue is complete:

1. Push your dedicated branch to your fork.
2. Open a pull request targeting `Second-Origin/PARTHA:dev`.
3. Use the existing [pull request template](.github/pull_request_template.md) — do not delete its sections.
4. Summarise what you implemented.
5. Link the issue.
6. Explain how you tested it, with the commands you ran.
7. Include screenshots or a recording for any visible UI change.
8. Identify configuration, migration, dependency, security, data, and compatibility implications.
9. Disclose dependencies and blocked work.
10. Request one reviewer: **`@parthrohit22`**.
11. Wait for approval and maintainer merge.

If GitHub permissions prevent you from assigning a reviewer, request review in the pull request description or a comment. CODEOWNERS may also request review automatically.

**You must not self-merge.**

### Issue-closing syntax

When a pull request **fully** completes an issue, its **description** must contain:

```text
Closes #123
```

The closing statement must be in the pull request description — not only in a commit message, and not only in a later comment.

Use `Closes`, `Fixes`, or `Resolves` **only** when every acceptance criterion is complete.

If the pull request is partial, use one of:

```text
Related to #123
Part of #123
Follow-up to #123
```

Do **not** use closing syntax when:

- any acceptance criterion remains incomplete
- tests required by the issue are missing
- documentation required by the issue is missing
- another pull request is still required
- the implementation deliberately changed scope
- any part of the work was deferred
- you cannot verify that the issue is actually solved

### Scope changes

If implementation reveals that the issue is inaccurate, unsafe, obsolete, blocked, or no longer achievable as written, you **must not** silently change scope.

You must:

1. Explain the discovery on the issue.
2. Update the pull request description.
3. State which acceptance criteria you completed.
4. State what remains incomplete.
5. Link any follow-up issues or dependent pull requests.
6. Ask whether the issue should be rewritten, split, superseded, or closed.

A pull request that does not fully solve its issue must not use closing syntax. Important scope changes belong in the pull request description — do not leave essential information only in review comments.

---

## 7. Review

After opening a pull request you must:

- wait for the automated checks
- respond to reviewer questions
- address requested changes
- keep the pull request focused on its issue
- update the description if scope changes
- keep the branch current with `dev`
- rerun tests after any rebase or conflict resolution
- wait for maintainer approval and merge

A reviewer approval does **not** override failing required checks.

Resolve a conversation only once the concern has actually been addressed, or a maintainer has made a decision. Do not resolve a reviewer's comment merely to clear the thread.

---

## 8. Merged branches are deleted

Merged branches may be deleted automatically. Assume your working branch disappears after merge.

Therefore you must:

- not leave unfinished work only on a branch that is being merged
- move unfinished work to a separate branch before merge
- not reuse a merged or deleted branch for unrelated work
- create follow-up branches from the latest `dev`
- preserve unmerged work in a dedicated dependent branch

---

## 9. Dependent and stacked branches

Dependent branches are allowed **only** when the work genuinely cannot be reviewed independently. Do not use stacked pull requests to avoid properly splitting an oversized issue.

1. Create the first branch from `upstream/dev`.
2. Create the dependent branch from the prerequisite branch.
3. Open the prerequisite pull request first.
4. State the dependency in the dependent pull request:

   ```text
   Depends on #<pr-number>
   ```

5. While the prerequisite is open, the dependent pull request may target the prerequisite branch, to keep its review diff clean.
6. Do not merge the dependent pull request before its prerequisite.
7. After the prerequisite merges:
   - `git fetch upstream`
   - rebase the dependent branch onto `upstream/dev`
   - resolve conflicts
   - rerun the relevant tests
   - push with `--force-with-lease`
   - retarget the dependent pull request to `dev`
   - verify the final diff contains only the dependent work

Every dependent pull request must link its issue, its prerequisite pull request, any follow-up pull request, and the required merge order.

---

## 10. Testing

Run the checks relevant to your change. These are what CI runs.

| Command | Runs | CI job |
| --- | --- | --- |
| `npm run test:backend` | Backend tests (pytest) | Backend |
| `ruff check app` · `ruff format --check app` · `mypy app` | Backend static analysis. Needs `requirements-dev.txt` — see the [backend README](apps/backend/README.md#static-analysis) | Backend |
| `python scripts/check-capabilities.py` | Capability registry and its generated README block are current and deterministic | Backend |
| `npm --prefix apps/frontend run test` | Frontend tests (vitest) | Frontend |
| `npm run lint:frontend` | ESLint | Frontend |
| `npm run build:frontend` | `tsc -b && vite build` — type errors surface here, not in lint | Frontend |
| `node scripts/dependency-audit.mjs` · `node --test scripts/dependency-audit.test.mjs` | Dependency audit policy and its own tests | Frontend |
| `npm --prefix apps/frontend run generate:api-contract -- --check` | Generated frontend DTOs have not drifted from the FastAPI schema | API Contract Drift |
| `npm run test:prototype` | Disposable fixtures plus the Playwright browser journeys | Prototype Browser Acceptance |
| `npm run test:accessibility` | The WCAG 2.2 AA baseline journeys only, on the same stack | Prototype Browser Acceptance |

`npm run build` runs the frontend build plus the backend tests. It does **not** run frontend lint or frontend tests — run those separately.

The table is the full CI gate list, so a change can pass `test:backend` and
`build:frontend` and still fail on contract drift, the capability registry, the
dependency audit, or a browser journey. If you touched a backend schema, run the
contract check; if you touched navigation or a page's structure, run
`test:accessibility`.

| If you changed… | You must run |
| --- | --- |
| Backend logic, services, intelligence, parsers | `npm run test:backend` |
| API request/response shape | `npm run test:backend`, update the frontend client and types, `npm run build:frontend` |
| Database models | Add an Alembic migration, then `npm run test:backend` (migration up/down is covered) |
| Frontend code | `npm run lint:frontend`, `npm --prefix apps/frontend run test`, `npm run build:frontend` |
| Local startup, CI, config, health | Smoke-check the affected backend/frontend start command and run the relevant tests above |
| Anything user-visible | Update the documentation **in the same pull request** |

Four backend tests are gated on real services and skip locally: two need `PARTHA_TEST_PG_URL` (the PostgreSQL analysis-job and refresh-token concurrency cases) and two need `PARTHA_TEST_REDIS_URL` (the Redis rate-limit backend cases). CI provides both services, so a locally green run showing four skips is expected rather than a problem.

If you cannot run a check locally, say so in the pull request and explain why. **Do not claim a check you did not run.**

### Migrations and breaking changes

- Every schema change ships an Alembic migration, and it **must downgrade cleanly** — the migration test enforces this.
- Never edit a migration that has already merged. Add a new one.
- Backfills belong in the migration, not in application startup.
- A breaking API change requires the design to be agreed on the issue first, and the frontend client and documentation updated in the same pull request.

---

## 11. Architectural rules

1. **Repository Intelligence is the shared repository-understanding boundary.** If a feature needs a repository fact, add reusable extraction to `app/intelligence/` and consume it from there.
2. **Consumers must not create separate repository parsers.** No walking the tree, no re-reading dependency manifests, no duplicating language or framework detection inside architecture, dependencies, review, documentation, export, or AI code.
3. **AI must remain an optional downstream consumer.** It must not read repository files or reinterpret the repository independently.
4. **Heuristic results must not be presented as guaranteed facts.** Most of what the engine infers — roles, modules, layers, symbols, frameworks — is inferred from paths and filenames. Label it accordingly in the API and the UI. See [Repository Intelligence](docs/architecture/REPOSITORY_INTELLIGENCE.md).
5. **Evidence must be represented only as precisely as the implementation supports.** PARTHA has file-level evidence and no line spans. Do not emit invented line numbers, placeholder citations, or fabricated success states to make output look grounded.
6. **Planned capabilities must not be documented as implemented.** An API field, a model, or a class name is not evidence that a capability exists.
7. **Backend resources must be owner-scoped wherever authentication applies.** Use the owner-scoped accessors, not the unscoped ones.
8. **Never expose secrets, credentials, or repository contents in logs.**
9. **Security-sensitive changes require explicit tests and reviewer attention.** Say so plainly in the pull request.
10. **Avoid unrelated refactors inside a scoped issue.** Drive-by cleanup makes a diff unreviewable. Open a separate issue.

**Current behaviour belongs in documentation. Future work belongs in GitHub issues.**

### Code standards

**Backend.** Keep routes thin and logic in services. Use schemas at the boundary. Preserve the standard error response shape. Avoid broad `except:` — catch what you can handle.

**Frontend.** Keep shell, features, and shared code separate. Reuse the shared API client and types. **No new `any`** — use `unknown` and narrow it. Preserve loading, empty, error, and success states.

**General.** Remove dead code. Avoid speculative abstractions. Never commit secrets, `.env` files, local databases, build outputs, or caches.

---

## 12. Definition of Ready

An issue is ready to be claimed and started only when:

- its objective is clear
- its acceptance criteria are testable
- the affected component is identifiable
- dependencies and blockers are recorded
- security and data implications are identified
- it is not already assigned
- a maintainer has acknowledged the claim

An issue failing any of these is not "almost ready" — it needs design, not an assignee.

---

## 13. Definition of Done

Work is complete only when:

- every claimed acceptance criterion is complete
- the implementation matches the agreed scope
- relevant tests are added or updated
- relevant tests pass
- documentation reflects the implemented behaviour
- security and data implications have been considered
- no credentials or sensitive information are committed
- the branch is rebased onto the latest `dev`
- the pull request contains no unrelated changes
- dependencies and follow-up work are linked
- the pull request description reflects the final outcome
- closing syntax is used only when the issue is fully resolved
- review feedback is addressed
- required checks pass
- the maintainer approves and merges the pull request

> **Code written does not mean issue completed.**

---

## 14. Conduct and licensing

All participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

PARTHA is licensed under the Apache License 2.0. By contributing, you agree your contribution is provided under that same license. Contribute only work you have the right to submit, and do not copy third-party code, images, fonts, datasets, or text into the project unless the license is compatible and the attribution is documented. There is currently no CLA or DCO requirement; if that changes, it will be documented here before being enforced.
