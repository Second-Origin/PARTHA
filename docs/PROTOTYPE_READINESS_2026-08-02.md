# PARTHA prototype readiness — 2 August 2026

This is the acceptance record for [issue #154](https://github.com/Second-Origin/PARTHA/issues/154)
and [PR #155](https://github.com/Second-Origin/PARTHA/pull/155). It describes executable
behaviour on `revamp-architecture`, not a future product plan.

> **Status: not merge-ready until independent review and required CI/CodeQL checks pass on the
> final head.** The branch must not be merged by its author.

## Capability matrix

| Surface | Classification | Repository source | Honest boundary |
| --- | --- | --- | --- |
| Register, login, repository import, analysis lifecycle | Ready | repository/database state | Authenticated and owner-scoped |
| Architecture | Ready | sealed `ri.v1` snapshot | Module/layer classification is heuristic; relationship states distinguish connected, unresolved, no observed relationships, and not extracted |
| Authentication explanation | Ready, limited | sealed `ri.v1` snapshot | Only the supported Python/FastAPI subgraph; every public claim is cited |
| Evidence Explorer | Ready | exact snapshot fact/span plus stored source hash | Fails closed when the fact, span, revision, or source hash does not match |
| Revision manifest | Ready | sealed `ri.v1` snapshot | Canonical content hash, not a digital signature |
| Engineering Review | Ready, limited | sealed `ri.v1` snapshot | `engineering-review.v2`; evidence-backed findings only; explicit category states; no score, grade, percentage, roadmap, or vulnerability scan |
| Insights | Ready, limited | sealed `ri.v1` snapshot | `repository-insights.v1`; defined snapshot-local counts and ratios only; no trend claims without history |
| Dependency Graph | **Preview** | legacy manifest analysis | Not snapshot-bound; direct declarations only; vulnerability/outdated assessment not computed |
| AI Workspace | **Preview** | mixed snapshot/legacy context | The built-in authentication explanation is cited from the sealed snapshot; free-form provider answers use legacy structure metadata and return no citations |
| Documentation | **Preview** | legacy heuristic analysis | Not bound to a sealed snapshot |
| Settings | Ready, limited | user configuration | Unavailable controls say so; no fabricated configuration |

Engineering Review and Insights are primary navigation destinations. They are not deferred and
do not fall back to `repo_metadata["intelligence"]`.

## Review contract

`GET /analysis/{repositoryId}/review` returns `engineering-review.v2` for the latest
owner-scoped sealed snapshot matching the selected repository revision.

Every finding includes:

- category and severity;
- human-readable explanation and deterministic remediation guidance;
- snapshot, fact, evidence, extractor, diagnostic, and rule identity;
- exact path and inclusive line span;
- `supportStatus`: `supported` when the span is the diagnostic's own recorded
  span, or `file_scoped` when the diagnostic named a file but no span.

A diagnostic becomes a finding only when the same snapshot holds evidence that addresses it: a
diagnostic with a span requires evidence at exactly that path and span, and a file-level
diagnostic requires that file's own file-granularity evidence record and is published as
`file_scoped` so a whole-file range is never presented as a line-addressed defect. A diagnostic
whose location cannot be established is omitted and counted, never published at a borrowed
span. The category matrix uses `assessed`, `partially_assessed`, `not_assessed`, and
`insufficient_evidence`, and the overall `assessmentStatus` is derived from that matrix rather
than fixed. Vulnerability scanning is a visible `not_assessed` category.

No response or report contains an overall score, category score, grade, health percentage, or
invented roadmap.

## Insights contract

`GET /analysis/{repositoryId}/insights` returns `repository-insights.v1` for the same
owner-scoped revision/snapshot identity used by Architecture and Review.

Published metrics have a stable ID, definition, unit, assessment state, and snapshot
provenance. Current metrics cover:

- file, symbol, and dependency node counts;
- resolved relationship and evidence-record counts;
- unresolved, ambiguous, unsupported, and malformed diagnostic counts;
- semantic-extraction coverage as an explicit numerator/denominator;
- relationship, diagnostic, language, and extractor breakdowns.

Vulnerability scanning is `not_assessed`. Change-over-time is exactly:
“Change-over-time insights are not available yet.” No activity, contributor, churn,
complexity, health, trend, or quality metric is invented.

## Architecture and responsive acceptance

The graph uses a readable 0.85 zoom floor. A busy semantic layer wraps deterministically into
subcolumns, so the 14-node single-layer fixture opens as a compact grid instead of a tall
single column. At the default view, browser tests require:

- every node label to be non-empty;
- rendered node geometry of at least 180×85 CSS pixels;
- effective label size of at least 10 CSS pixels;
- no node overlap;
- sensible row/column distribution;
- a visible primary flow on the small fixture;
- a minimap whenever all nodes cannot fit.

Keyboard users can Tab to nodes, see a browser-painted focus ring, press Enter or Space to open
the inspector, and Escape to close it with focus returned. Fit and Reset Layout preserve
readability. At 390×844, the page has no horizontal document scroll, a complete node remains
visible, graph controls and minimap are reachable, and the modal navigation drawer traps focus,
closes with Escape, and returns focus to its trigger.

The repository selector is a named listbox with selected state, arrow/Home/End navigation,
Escape handling, and focus return. Review and graph inspectors are modal dialogs with focus
containment, Escape handling, and focus restoration.

## Reproducible fixtures and browser gate

The fixture seeder creates only repositories owned by the fixed disposable fixture account,
deletes only that account’s prior repositories, writes credentials to a mode-0600 temporary
manifest, and never prints the password or access token. It creates:

| Fixture | Acceptance purpose |
| --- | --- |
| `small` | primary architecture flow and identity |
| `medium` | multi-layer graph and focus |
| `large-multi` | dense multi-layer graph |
| `large-single` | 14-node single-layer wrapping and no-finding Review |
| `long-labels` | truncation plus recoverable accessible name |
| `disconnected-unresolved` | disconnected module, unresolved diagnostic, supported Review finding, Insights diagnostic |
| `unanalysed` | honest no-snapshot state |

From a clean checkout with backend/frontend dependencies installed, this one command starts
isolated SQLite/storage, starts both servers, recreates fixtures, runs all Playwright journeys,
then stops the processes and removes temporary state:

```bash
npm run test:prototype
```

The same runner is a required `Prototype Browser Acceptance` CI job. CI installs Chromium and
uploads the Playwright HTML report, traces, and failure screenshots.

To refresh reviewable screenshots locally:

```bash
PARTHA_VISUAL_SCREENSHOT_DIR=docs/screenshots/prototype \
  node scripts/run-prototype-acceptance.mjs
```

The browser suite covers four graph sizes, long labels, focus/open/close behaviour, fit/reset,
narrow viewport navigation, the no-snapshot state, manifest identity, Review finding and
no-finding states, authentic evidence navigation, Insights definitions, cross-surface identity,
rapid repository switching, and cross-owner 404 responses.

### Committed review evidence

- Architecture: [small flow](screenshots/prototype/architecture-small.png),
  [dense multi-layer](screenshots/prototype/architecture-large-multi.png),
  [14-node single layer](screenshots/prototype/architecture-large-single.png),
  [keyboard focus](screenshots/prototype/architecture-keyboard-focus.png),
  [narrow viewport](screenshots/prototype/architecture-narrow-viewport.png),
  [no-snapshot state](screenshots/prototype/architecture-empty-state.png), and
  [revision manifest](screenshots/prototype/revision-manifest.png).
- Engineering Review: [exact evidence destination](screenshots/prototype/review-supported-finding-evidence.png)
  and [zero findings with explicit not-assessed categories](screenshots/prototype/review-no-findings-not-assessed.png).
- Insights: [defined snapshot metrics and provenance](screenshots/prototype/insights-defined-metrics.png).

## Verification commands

```bash
# Backend, local fallbacks (PostgreSQL/Redis-gated tests skip with explicit reasons)
npm run test:backend

# Backend with the same external services as CI
PARTHA_TEST_PG_URL=postgresql+psycopg://partha:partha@localhost:5432/partha_test \
PARTHA_TEST_REDIS_URL=redis://localhost:6379/0 \
  apps/backend/.venv/bin/python -m pytest

npm --prefix apps/frontend run lint
npm --prefix apps/frontend run test
npm --prefix apps/frontend run build
npm run test:prototype
```

The PR description records the exact final counts and check URLs for the pushed head.

## Five-minute founder demo

1. Open Architecture on `small`; identify the upload revision and sealed snapshot in the
   manifest, then show the readable primary flow.
2. Switch to `large-single`; show the compact grid, minimap, Tab focus, Enter/Space inspector,
   Escape, Fit View, and Reset Layout.
3. Open Engineering Review on `disconnected-unresolved`; state that there is no score. Open the
   supported unresolved-relationship finding and follow its exact evidence link.
4. Switch Review to `large-single`; show zero evidence-backed findings alongside the
   `Not assessed` vulnerability-scanning category.
5. Open Insights; read one metric definition, its exact count, the unresolved diagnostic
   breakdown, snapshot identity, and the unavailable change-history statement.
6. Move among Architecture, Review, and Insights and show that revision and snapshot identity
   are unchanged. Rapidly switch repositories and show that old identity/data disappears while
   the new request loads.
7. Open Dependency Graph and read the Preview limitation: legacy manifest path, not
   snapshot-bound, no security scan.

## Known limitations

- Snapshot extractors support documented Python and TypeScript/JavaScript constructs only.
  Unsupported or ambiguous constructs remain diagnostics, not guesses.
- Architecture module/layer classification is heuristic even though its relationship facts are
  snapshot-backed.
- Review is a deterministic view of supported diagnostics, not a comprehensive engineering or
  security assessment. No vulnerability scanner runs.
- Insights is a snapshot inventory. There is no revision-history comparison, trend analysis,
  contributor analysis, churn, complexity, or health score.
- Dependency Graph, AI Workspace, and Documentation remain Preview legacy consumers.
- The manifest digest proves content integrity against this deployment’s stored snapshot. It
  does not prove authorship and is not a signature.
- AI receives no source content or line numbers and returns no citations.
- The prototype has not been operated as a hardened multi-tenant production deployment.

## Rollback

The work is additive and has no destructive data migration. Revert the issue-linked commits in
reverse order. If only Review/Insights must be removed, revert their route/dependency wiring,
frontend surfaces, and schemas together; leaving a UI or report consumer on the old contract is
not a valid partial rollback. Preview classifications live in
`apps/frontend/src/app/routes/productSurfaces.tsx` and must remain visible if those legacy
surfaces stay reachable.

Administrator direction on 25 July 2026 explicitly rejected deferring Review and Insights.
Rollback must not silently restore a deferred placeholder or the legacy score-based Review.
