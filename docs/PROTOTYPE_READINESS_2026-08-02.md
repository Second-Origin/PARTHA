# PARTHA Prototype Readiness — 2 August 2026

This document records **verified runtime behaviour**, not intended behaviour. Every number in
it came from a run that is reproducible with the commands below.

| | |
|---|---|
| Umbrella issue | [#154](https://github.com/Second-Origin/PARTHA/issues/154) |
| Pull request | [#155](https://github.com/Second-Origin/PARTHA/pull/155) — open, **not merged** |
| Branch | `revamp-architecture` → `dev` |
| Base commit | `30df93917cb6c546bd0b155aee9ba7b5c4c7e3ae` |
| Head at time of writing | `ab5a5df` (later commits on this branch may follow; the PR carries the current head) |
| Verified on | 25 July 2026 — macOS (Darwin 25.5.0), Python 3.13.13, Node 22, PostgreSQL 15/16, Redis 8, Chromium 151 |

> **Status: not merge-ready.** Automation is green and visual acceptance has been performed,
> but the administrator decisions in §11 are outstanding and an independent review is required.

---

## 1. Implemented scope

| Priority | Delivered |
|---|---|
| 1 — Remove misleading behaviour | `/ai/stream` pseudo-stream deleted; suggestions return empty; "Real data" badge replaced with the authentic repository source; whole-product sweep; legacy provenance declared and displayed |
| 2 — Bound snapshot reads | Architecture fact query restricted by predicate, diagnostic code, assertion predicate and node kind; observations no longer hydrated; evidence lookups batched at 500 |
| 3 — Architecture graph usability | Layered left-to-right layout, larger nodes, deterministic positions, collapse/filter (from #152); accessible names, tooltips for truncated labels, keyboard focus, pane panning; readable zoom floor for dense graphs |
| 4 — Hidden surfaces | AI Workspace and Documentation restored as **Preview**; Engineering Review and Insights remain **deferred**, each with a recorded reason |
| 5 — Revision verification | `GET /analysis/{id}/revision-manifest` and `POST .../verify`, with a copy/export panel on the Architecture page |
| 6 — Dependency and frontend quality | react-router-dom 6→7.18.1, dompurify 3.4.12, brace-expansion 5.0.8; policy-aware CI audit gate with its own tests; coverage thresholds ratcheted; accessibility smoke checks over every active route |
| 7 — Journey proof | Flagship journey executed against a live backend on PostgreSQL, plus a committed end-to-end test and a browser-driven visual suite |

---

## 2. Capability matrix

| Surface | Classification | Intelligence source | Basis |
|---|---|---|---|
| Register / Login | Ready | n/a | Live smoke + backend tests |
| Repositories | Ready | n/a | Owner-scoped, verified in journey |
| Upload / GitHub import | Ready | n/a | Journey step 5; revision identity at step 6 |
| Analysis lifecycle | Ready | writes snapshot + legacy blob | Durable job completed and cancelled in live runs |
| Architecture graph | Ready | **`ri.v1` snapshot only** | Journey step 8; visual acceptance at 3 sizes |
| Authentication explanation | Ready | **`ri.v1` snapshot only** | Journey step 9; 4 claims, 4 citations, 1 chain |
| Evidence source viewer | Ready | **`ri.v1` snapshot only** | Journey step 11; content hash verified against seal |
| Revision manifest | Ready | **`ri.v1` snapshot only** | Journey steps 12–13; digest stable across restart |
| Dependency graph | Ready, **legacy disclosed** | legacy heuristic | Declares `legacy-heuristic` provenance + Preview notice |
| Settings | Ready | n/a | Inert "Coming Soon" controls, no fabricated data |
| **AI Workspace** | **Preview** | legacy repository context | Route, auth, ownership verified; fails closed with 422 when no provider |
| **Documentation** | **Preview** | legacy heuristic | Route, auth, ownership verified; limitation displayed |
| Engineering Review | **Deferred** | legacy heuristic | `review_service` derives 0–100 scores as `100 − Σ severity cost`; not evidence-derived |
| Insights | **Deferred** | none | No backend endpoint exists at all |

---

## 3. Exact test evidence

### Backend — PostgreSQL + Redis available

```
PARTHA_TEST_PG_URL=... PARTHA_TEST_REDIS_URL=... pytest
710 passed, 0 skipped, 12 warnings in 35.69s
```

Baseline was 695 passed / **4 skipped**; those 4 were 2 PostgreSQL concurrency and 2 Redis
rate-limit tests, both now executed. Delta: −4 (`/ai/stream` tests removed with #148),
+2 (#150 bounding), +1 (dependency provenance), +9 (revision manifest), +3 (prototype
journey), +4 (previously skipped) = **710**.

Without services (`pytest` alone): **706 passed, 4 skipped** — the same 4, each skipping with
an explicit reason naming the missing environment variable (`PARTHA_TEST_PG_URL`,
`PARTHA_TEST_REDIS_URL`).

### Frontend

```
Test Files  26 passed (26)
     Tests  143 passed (143)

Statements   : 46.02%   Branches : 38.46%
Functions    : 39.84%   Lines    : 47.91%
```

Baseline was 119 tests at 35.94 / 30.71 / 30.75 / 37.32. Thresholds raised from
`1.5 / 0.25 / 2 / 1.5` to `45 / 37 / 39 / 47`, which the current run clears.

| Check | Result |
|---|---|
| `eslint .` | Pass, 0 problems |
| `tsc -b` | Pass, 0 errors |
| `vite build` | Pass |
| Dependency-audit policy tests (`node --test scripts/dependency-audit.test.mjs`) | **9 passed** |
| `node scripts/dependency-audit.mjs` | Pass — 1 acknowledged, 0 blocking |
| Visual acceptance (`test:visual`) | **8 passed** |

### Branch CI — PR #155

| Job | Result |
|---|---|
| Repository Hygiene | pass |
| Frontend (install → policy tests → audit → lint → test → build) | pass |
| Backend (PostgreSQL 16 + Redis service containers) | pass — 710 passed, 0 skipped |
| Repository Intelligence golden benchmark | pass — precision 1.0000 |
| Docker Compose (build, config, startup, readiness, shutdown) | pass |
| CodeQL — JavaScript/TypeScript and Python | pass |

Docker is not installed on the development machine, so Compose evidence comes from CI.

Two CI failures occurred during this work and neither was hidden: a real lockfile/`package.json`
drift after `axe-core` was added (fixed), and a Docker Hub pull timeout during container
initialisation, before checkout (re-run).

---

## 4. Live journey results

Backend on PostgreSQL, Redis, throwaway storage directory.

| # | Step | Result |
|---|---|---|
| 1–2 | `/health`, `/ready` | `ok` / `ready` with database and storage checks |
| 3 | Register | 201 |
| 4 | Anonymous `/repositories` | **401** |
| 5 | Import archive | 201 |
| 6 | Revision identity | `upload sha256:48a60c28…` — present before any analysis |
| 7 | Durable analysis | queued → `completed` |
| 8 | Architecture | sealed snapshot `snap_a5d2f1a2…`, 7 nodes, 6 edges |
| 9 | Authentication answer | `ready`, 4 claims, 4 citations, 1 chain |
| 10 | Citation binding | all 4 citations reference the analysed snapshot |
| 11 | Open cited source | `src/routes.py:7-7`, content served and hash-verified |
| 12 | Revision manifest | `verified`, 6 named/versioned extractors |
| 13 | Manifest verification | unaltered → `verified`; tampered → `mismatch` |
| 14 | Legacy disclosure | dependencies declare `legacy-heuristic` |
| 15 | Cross-owner isolation | 4 routes → **404**, second owner's list empty |
| 16 | AI without provider | **422**, no simulated answer |

**Restart persistence** — server killed and restarted against the same database: architecture
resolved to the same snapshot, the manifest digest was **byte-identical**, the explanation kept
its 4 claims and 4 citations, and the analysis job stayed `completed`.

**Failure and cancellation states**

| Case | Result |
|---|---|
| Unknown repository | 404 |
| Inverted line span | 422 |
| Fabricated fact id on a real snapshot | 200 `status: unavailable`, `content: null` |
| Cancel a running analysis | 200 → `cancelled`, persists |
| Architecture with no sealed snapshot | `relationshipSnapshotId: null` + `ARCH-REL-NOT-EXTRACTED` |

---

## 5. Visual acceptance (#112)

Performed in Chromium 151 at 1440×900 against a live backend. Evidence is committed under
[`docs/screenshots/architecture/`](screenshots/architecture/).

| Fixture | Shape | Result |
|---|---|---|
| small | 5 nodes, 2 edges, 1 disconnected | Readable, layered, no overlap |
| medium | 6 nodes, 16 edges, 5 layers, 1 unresolved import, 1 very long module name | Readable, labels truncate with full text in tooltip and accessible name |
| large | 14 nodes, **260 edges**, single layer | Readable after the zoom-floor fix; overflows the viewport and is navigated with the minimap |
| unanalysed | no sealed snapshot | Honest empty state, no fabricated graph |

Checked: initial fit-to-view, default-zoom readability, node overlap, label truncation and
recovery, layer ordering, keyboard reachability with a focus indicator, narrow viewport
(390×844, no horizontal page scroll), empty state, and the revision manifest with its
content-hash wording.

**Two real defects were found and fixed here**, both of which unit tests and axe had passed:

1. The revision manifest panel consumed most of the Architecture page, leaving the graph a
   ~130px strip. It is now collapsed by default.
2. On the dense fixture, fit-to-view scaled to ~0.15 and rendered nodes at ~36×17px — #112's
   original symptom, surviving at scale. Fit-to-view now has a readable zoom floor.

**Known remaining limitation:** when every module lands in a single layer (as in the large
fixture), the layered layout produces one tall column and leaves horizontal space unused. It is
readable and navigable, but not well composed. Tracked as follow-up work on #112; it is a
quality issue, not a correctness or legibility one.

---

## 6. Security acceptance

| Advisory | Status |
|---|---|
| `brace-expansion` DoS (high, dev-only) | **fixed** — override `^5.0.8` |
| `dompurify` GHSA-c2j3-45gr-mqc4 (low ×2) | **fixed** — override `3.4.12` |
| `react-router` GHSA-wrjc-x8rr-h8h6 open redirect (moderate) | **fixed** — 7.18.1 |
| `react-router-dom` GHSA-jjmj-jmhj-qwj2 (moderate) | **fixed** — 7.18.1 |
| `react-router` GHSA-qwww-vcr4-c8h2 RSC CSRF (high) | **accepted until 2026-10-01** |

**GitHub lists React Router 8.3.0 as patched** (affected `>=7.12.0, <8.3.0`). PARTHA
temporarily remains on 7.18.1 because the patched major version has not yet been validated
against the current React 18 prototype:

- `react-router@8.3.0` declares `peerDependencies` `react>=19.2.7`, `react-dom>=19.2.7`;
  PARTHA is on React 18.3.1.
- `react-router-dom` has **no 8.x release** (latest 7.18.1), and all 33 React Router import
  sites in the frontend import from `react-router-dom`.

Adopting 8.3.0 therefore means a React 19 migration plus a routing-wide import change — out of
scope before 2 August. The affected behaviour is restricted to unstable RSC APIs, which PARTHA
does not import or enable; it is a client-only Vite SPA on `createBrowserRouter` with no
server-side React Router runtime. **This acceptance does not claim that no patched version
exists.**

An earlier revision of this branch stated "No fixed release exists at any version". That was
wrong — it read npm's "No fix available" as proof no patch existed, when npm reports that when
it cannot apply a fix automatically. The claim is retracted and corrected in `ec7760c`.

The gate fails if the acceptance expires, if the advisory stops naming `react-router`, if the
lockfile moves `react-router` off `7.18.1`, if frontend source starts using an unstable or
server-side React Router surface, or if the acknowledgement is left behind after the advisory
disappears. Nine tests cover those conditions.

---

## 7. Authentic-source guarantees

- Architecture, the authentication explanation, the evidence viewer and the manifest read
  **only** the sealed `ri.v1` snapshot — no working-tree read, no legacy fallback.
- Every citation carries `snapshotId`, `factId`, `path`, `startLine`, `endLine`, and was
  verified to belong to the snapshot the manifest names.
- `has_evidence_reference` rejects a citation whose fact does not match its span, so a deep
  link cannot keep a genuine snapshot and substitute a different fact.
- The evidence viewer recomputes the file content hash against the sealed hash and refuses to
  serve changed content.
- Legacy surfaces declare `legacy-heuristic` provenance in the response body and render the
  limitation.
- The manifest digest is a canonical-JSON SHA-256, described as a content hash and explicitly
  **not** a digital signature. A test asserts that wording.

---

## 8. Clean-start instructions

```bash
# services
brew services start postgresql@15 && brew services start redis
createdb partha_dev

# backend
cd apps/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DATABASE_URL="postgresql+psycopg://$(whoami)@localhost:5432/partha_dev" \
STORAGE_PATH=./.local/storage AUTO_CREATE_TABLES=1 \
JWT_SECRET_KEY=<32+ random chars> PROVIDER_KEY_SECRET=<32+ random chars> \
.venv/bin/python -m uvicorn app.main:app --port 8000

# frontend
npm ci --prefix apps/frontend
VITE_API_URL=http://localhost:8000 npm --prefix apps/frontend run dev
```

Full verification:

```bash
PARTHA_TEST_PG_URL="postgresql+psycopg://$(whoami)@localhost:5432/partha_test" \
PARTHA_TEST_REDIS_URL="redis://localhost:6379/0" \
  apps/backend/.venv/bin/python -m pytest      # 710 passed, 0 skipped

npm --prefix apps/frontend run test            # 143 passed
node --test scripts/dependency-audit.test.mjs   # 9 passed
node scripts/dependency-audit.mjs              # 0 blocking
```

### Reproducing visual acceptance

The visual suite needs a running backend, a running frontend and seeded fixtures. Use the same
origin host for both (the access token is held in memory and the refresh cookie is host-bound,
so mixing `localhost` and `127.0.0.1` will bounce you to the login page):

```bash
npx --prefix apps/frontend playwright install chromium
# seed small / medium / large / unanalysed fixtures against the running backend,
# writing credentials and repository ids to /tmp/visual-fixtures.json
VITE_API_URL=http://localhost:8000 npm --prefix apps/frontend run dev
npm --prefix apps/frontend run test:visual
# to refresh the committed evidence:
PARTHA_VISUAL_SCREENSHOT_DIR=docs/screenshots/architecture \
  npm --prefix apps/frontend run test:visual
```

---

## 9. Five-minute founder demo

1. **Register** — show the 401 on `/repositories` first, then register. *(30s)*
2. **Import** — upload a small TypeScript or Python repository. Point at the `sha256:` revision
   value: identity exists before any analysis. *(45s)*
3. **Analyse** — start analysis; show it enqueue and complete durably. *(45s)*
4. **Architecture** — open the graph. Readable at default zoom, left-to-right, Tab between
   modules. *(60s)*
5. **Revision manifest** — the bar above the graph shows `verified` and the snapshot id. Open
   Details: six named and versioned extractors, canonical graph hash. Copy it. Say plainly:
   content hash, not a signature. *(45s)*
6. **Ask the authentication question** — "Explain Authentication". Four claims, each with a
   `path:line` citation. *(45s)*
7. **Open a citation** — the exact source span, verified against the sealed content hash. *(30s)*
8. **Close the loop** — the citation's snapshot id equals the manifest's snapshot id. That is
   the product's whole claim, on screen. *(20s)*
9. **Show a limit honestly** — open Dependency Graph and read the Preview notice: legacy engine,
   not snapshot-backed. *(20s)*

---

## 10. Known gaps

1. **Two intelligence truths remain.** Dependency graph, documentation, engineering review and
   AI context still use the legacy engine. This work discloses that rather than migrating it.
2. **Manifest verification is deployment-scoped.** The digest proves integrity against this
   deployment's stored snapshot. It is not signed, so it proves neither authorship nor
   protection against an operator who can modify the database. (#113 stays open.)
3. **Single-layer graphs compose poorly** — readable, but one tall column with unused
   horizontal space. (#112 follow-up.)
4. **Accessibility is a smoke check, not a WCAG 2.2 AA baseline.** Colour contrast and
   screen-reader journeys are unverified. (#118 stays open.)
5. **The visual suite is not in CI.** It needs a backend, seeded fixtures and a browser
   download; it is an explicit local gate.
6. **Docker is unavailable on the development machine.** Compose evidence is CI-only.
7. **Engineering Review and Insights are unavailable**, not fixed.
8. **Frontend coverage is 46.02%.** Many pages and hooks remain unexecuted.
9. **Lockfile inconsistency.** The workspace root declares workspaces but has no lockfile, so a
   plain `npm audit` fails `ENOLOCK`; everything uses `--prefix apps/frontend`. The monorepo
   dependency layout was deliberately left alone.
10. **Canonical status reconciliation is incomplete** — this document is not yet generated from
    capability evidence. (#117 stays open.)

---

## 11. Rollback

- Revert the merge commit: `git revert -m 1 <merge-sha>`, or revert individual commits — each
  is small and single-purpose.
- **No data repair is needed.** The work is additive: no destructive migration, and the manifest
  endpoints are read-only.
- To hide a restored surface without touching its code, set its `readiness` to `'deferred'` in
  `apps/frontend/src/app/routes/productSurfaces.tsx` — one line.
- To revert the dependency work alone, restore `apps/frontend/package.json` and
  `package-lock.json` and rerun `npm ci --prefix apps/frontend`.

---

## 12. Decisions awaiting administrator approval

These are **recommendations, not decisions**. None has been approved.

1. Removal of `POST /ai/stream` as an intentional breaking API change.
2. The temporary React Router risk acceptance (8.3.0 deferred; expires 2026-10-01).
3. AI Workspace returning as **Preview** on legacy repository context.
4. Documentation returning as **Preview** on legacy heuristics.
5. Engineering Review and Insights remaining **deferred** through 2 August.
6. Architecture graph visual acceptance — evidence is in §5 and
   [`docs/screenshots/architecture/`](screenshots/architecture/); sign-off is still yours.
7. Manifest wording: "canonical content hash, not a digital signature".

Independent review of PR #155 is also required; it has not been approved by its author and must
not be.
