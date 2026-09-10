# PARTHA capability matrix

**Generated — do not edit the table below by hand.**

The table between the two `GENERATED CAPABILITY REGISTRY` markers is spliced from
the authoritative capability registry in
[`apps/backend/app/extraction/support_matrix.py`](../apps/backend/app/extraction/support_matrix.py).
CI runs `python scripts/check-capabilities.py` (also in the release workflow) and
fails if this file drifts from that source; regenerate with
`python scripts/check-capabilities.py --write`.

This is the detailed contract. The root [README](../README.md#what-partha-does) carries
a short prose summary and links here. Roadmap items and explicit non-goals live in
[ROADMAP.md](../ROADMAP.md).

## How to read it

- **Implemented** — the workflow exists and is executable on the branch you are reading.
- **Implemented with disclosed limits** — it exists, with an explicit coverage or trust boundary stated in the row.
- **Planned** — roadmap work; current responses report an explicit not-available state rather than a fabricated answer.
- **Rejected** — intentionally outside the product contract.

Statuses describe the branch you are reading:
[`main`](https://github.com/Second-Origin/PARTHA/tree/main) carries the latest tagged
release; `dev` carries active development.

## Registry

<!-- BEGIN GENERATED CAPABILITY REGISTRY -->
| Capability | Status | Current boundary |
| --- | --- | --- |
| Archive upload and public GitHub import | **Implemented** | ZIP/TAR-family archives and shallow public GitHub HTTPS clones; size and path-safety limits apply. Private GitHub cloning and other repository hosts are not supported. |
| Repository explorer | **Implemented** | Owner-scoped file tree plus bounded text/image preview, binary detection, and truncation. |
| Authentication and owner isolation | **Implemented** | Email/password, Argon2, short-lived access tokens, rotating refresh tokens with reuse detection. Google and GitHub OAuth sign-in and account linking are implemented but inert until provider credentials are configured, and never create an account. Registration is gated by an admin-managed email allowlist in every environment, except the first account on an empty instance. Protected resources are owner-scoped; non-owner access returns 404. |
| Analysis lifecycle | **Implemented** | Database-backed, cancellable job with progress, bounded retry, lease renewal, and stale-worker recovery. |
| Repository Intelligence | **Implemented with disclosed limits** | Immutable, revision-addressed `ri.v1` snapshots with normalized facts, evidence, query APIs, and a total canonical graph hash. Semantic extraction is strongest for supported Python and TypeScript/JavaScript constructs. |
| Repository lineage | **Implemented with disclosed limits** | Repeated imports of the same repository and branch are grouped into a durable, owner-scoped lineage with duplicate-revision detection (RFC-0002). `GET /repositories/{id}/lineage` returns the ordered history and the repository detail page renders it. Refresh and cross-revision comparison on top of a lineage are not built. |
| Architecture and authentication explanation | **Implemented with disclosed limits** | Interactive snapshot-backed graph. Module/layer classification is heuristic. The cited authentication subgraph covers supported Python/FastAPI patterns only. |
| Dependency Graph | **Implemented with disclosed limits** | Direct declarations from `package.json`, `pyproject.toml`, and `requirements.txt` plus resolved pins from `package-lock.json` and `poetry.lock`, merged onto one dependency identity with repeated workspace declarations and exact spans. A lockfile pin is recorded as a resolution, never as a direct dependency edge, so transitive resolution is still not claimed. |
| Service-interaction discovery | **Implemented with disclosed limits** | Outbound HTTP call sites on `requests`, `httpx`, `fetch`, and `axios` resolve to a service node identified by its absolute origin, with the literal method and path on the call's own observation. A computed, relative, or shadowed destination is a diagnostic, never an edge. |
| Infrastructure-as-code resources | **Implemented with disclosed limits** | Declared Docker Compose services, volumes, and networks with their exact declaration spans. Templated values are disclosed rather than reported as observed, and no other IaC format is read. |
| Engineering Review | **Implemented with disclosed limits** | `engineering-review.v2`; evidence-addressed findings and explicit category states. No overall score, grade, health percentage, vulnerability result, or generated roadmap. |
| Repository Insights | **Implemented with disclosed limits** | `repository-insights.v1`; defined counts, ratios, diagnostics, language breakdowns, and extraction coverage from one snapshot. No change-over-time claims. |
| Documentation and report export | **Implemented with disclosed limits** | Documentation uses current-revision structural facts. Review, Documentation, Architecture, and Dependencies export through one JSON/Markdown/HTML/PDF pipeline. |
| AI provider integration | **Implemented with disclosed limits** | Per-user configuration for supported providers, encrypted API keys, and constrained outbound destinations. Free-form answers receive structural facts and observed paths—not source bytes or line spans—and return no automatic citations. |
| Asynchronous processing | **Implemented with disclosed limits** | Analysis runs off the request path. Import, extraction of the initial archive/clone, and file-tree parsing remain synchronous; one in-process worker handles analysis jobs. |
| Incremental re-analysis and revision comparison | **Planned** | The full repository is analysed again; no snapshot-to-snapshot product workflow is available. |
| Change-impact or blast-radius analysis | **Implemented with disclosed limits** | Owner-scoped traversal over one sealed snapshot's resolved import and dependency edges. It does not compare revisions or calculate churn or trends. |
| Vulnerability and outdated-dependency scanning | **Planned** | Dependency responses report explicit `not_computed` states; Review keeps vulnerability scanning `not_assessed`. No clean bill of health or zero count is fabricated. |
| Grounded, cited free-form AI answers | **Planned** | Provider answers are intentionally uncited because providers do not receive source content or line numbers. |

**Implemented with disclosed limits** means the workflow exists with an explicit coverage or trust boundary. **Planned** means it is roadmap work and current responses do not manufacture an answer. **Rejected** means the capability is intentionally outside the product contract.
<!-- END GENERATED CAPABILITY REGISTRY -->

## Boundaries worth stating plainly

The registry rows are precise, but three distinctions are easy to misread:

- **Repository lineage is revision *history*, not revision *comparison*.** Repeated imports
  are grouped and browsable; there is no `Snapshot A ↔ Snapshot B` graph diff, no rename or
  move detection, and no cross-revision entity correspondence. See
  [RFC-0002 §1.3](architecture/REPOSITORY_LINEAGE_RFC.md#13-implementation-status).
- **Change-impact analysis is single-snapshot reachability.** It traverses resolved import
  and dependency edges inside one sealed snapshot. It does not compare revisions, compute a
  historical blast radius, or calculate churn or trends.
- **Stable keys are intra-snapshot.** They identify an entity *within* one snapshot for
  reference and hashing; they are not a guarantee that the same entity can be matched across
  revisions after a refactor ([RFC-0001 §4.1](architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md#41-principle-and-cross-revision-guarantees)).

For the full extraction boundary — what each extractor reads, what it refuses, and where
evidence stops — read [Repository Intelligence](architecture/REPOSITORY_INTELLIGENCE.md).
