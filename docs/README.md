# PARTHA Documentation

Maintained guides describe the system as it currently exists. RFCs describe accepted engineering
design contracts and must label what is accepted, implemented, and deferred. Historical QA records
are point-in-time evidence, not current-state documentation.

**Current behaviour belongs in documentation. Future work belongs in GitHub issues.** If you find a claim the code does not support, that is a bug — please open an issue.

## Index

| Document | Reader | Purpose |
| --- | --- | --- |
| [README](../README.md) | Anyone evaluating or running PARTHA | What PARTHA is, what currently works, how to run it locally, and its limitations. |
| [CONTRIBUTING](../CONTRIBUTING.md) | Contributors | The contribution rules: fork-first workflow, claiming an issue, branch naming, rebasing, pull requests, Definition of Ready and Done. Read before opening a PR. |
| [Local development and troubleshooting](DEVELOPMENT.md) | New contributors | A single walkthrough for starting the backend and frontend, running every test/lint/build command, the local database and API-contract failures you're most likely to hit and how to fix them, and how to report a reproducible issue. |
| [SECURITY](../SECURITY.md) | Anyone reporting a vulnerability | How to disclose privately. Never open a public issue for a vulnerability. |
| [AI provider egress policy](security/AI_PROVIDER_EGRESS.md) | Operators and backend contributors | Deployment-owned provider destination policy, DNS pinning, redirect handling, safe defaults, and required production network controls. |
| [Connecting an AI provider](operations/AI_PROVIDER_SETUP.md) | Anyone enabling the optional AI workspace | The end-to-end setup path (Settings and the `ai/*` API), per-provider requirements, the egress-policy prerequisite for a local or custom Ollama endpoint, Ollama's slow-first-request and one-at-a-time behaviour, and a troubleshooting table. |
| [Database migration rehearsal and recovery](operations/DATABASE_MIGRATION_REHEARSAL.md) | Operators and backend contributors | Disposable Alembic rehearsal command, supported baseline evidence, production preflight, and truthful restore-based recovery decisions. |
| [WCAG 2.2 AA accessibility baseline](accessibility/WCAG_2_2_AA_BASELINE.md) | Frontend contributors and accessibility reviewers | Reproducible automated coverage for the Phase 0 journeys, the outstanding human verification checklist, confirmed findings, and linked follow-up issues. |
| [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) | Everyone | Expected conduct and how to report a violation. |
| [System Overview](architecture/SYSTEM_OVERVIEW.md) | Contributors and maintainers | Current components, ingestion flow, persistence, consumers, trust boundaries, and architectural limitations. |
| [Repository Intelligence](architecture/REPOSITORY_INTELLIGENCE.md) | Anyone changing analysis behaviour | What is extracted, what is deterministic versus heuristic, how facts are persisted, who consumes them, what consumers must not do, and where evidence and provenance stop. **Read this before touching analysis.** |
| [Repository Intelligence v1 RFC](architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md) | Contributors on the intelligence track | **Accepted** architectural contract (RFC-0001, tracking [#86](https://github.com/Second-Origin/PARTHA/issues/86)) for the snapshot/evidence schema: deterministic entity keys, separate inferred assertions, complete derivation chains, producer identity and producer-version tracking, provenance, immutability, diagnostics, versioning, and total canonical graph hashing. **Status: Accepted** — independently approved by [@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24) on [Issue #86](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780) and [PR #101](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647) on 2026-07-16. The durable snapshot pipeline and product-consumer migration are implemented; §17 tracks the remaining contract gaps. |
| [Repository Intelligence relationship resolution](architecture/REPOSITORY_INTELLIGENCE_RESOLUTION.md) | Contributors changing extraction or resolution | The deterministic resolver (Issue [#91](https://github.com/Second-Origin/PARTHA/issues/91)): how stored observations become `resolved` edges, the one/zero/many candidate outcomes, and the `RI-RES-UNRESOLVED` / `RI-RES-AMBIGUOUS` diagnostics emitted instead of a guess. |
| [Repository Lineage RFC](architecture/REPOSITORY_LINEAGE_RFC.md) | Contributors on the intelligence track | **Accepted design, implemented** (RFC-0002, tracking [#298](https://github.com/Second-Origin/PARTHA/issues/298)) for owner-scoped repository lineage identity, unlineaged standalone imports, 1-based never-reused sequence allocation, deletion behavior, and database-enforced membership integrity. Landed in [#299](https://github.com/Second-Origin/PARTHA/pull/372) (migrations `0013_lineage_expand` / `0014_lineage_constraints`); the `GET /repositories/{id}/lineage` read API ([#400](https://github.com/Second-Origin/PARTHA/pull/407)) and the repository-detail Lineage History UI followed. Refresh and cross-revision comparison on top of a lineage are not built. Revision identity remains governed by RFC-0001 §3. |
| [Repository Lineage migration plan](architecture/REPOSITORY_LINEAGE_MIGRATION_PLAN.md) | Anyone auditing the lineage migration | The implementation-grade plan the [#299](https://github.com/Second-Origin/PARTHA/pull/372) migration was built and tested against: current-state schema, Alembic/backfill, ownership, deletion, concurrency, validation, and rollback. RFC-0002 owns the architecture decisions; this document is the migration and test record and contains no runtime change. |
| [Repository Intelligence golden benchmark](../apps/backend/tests/benchmark/README.md) | Contributors on the intelligence track | The versioned golden fixture corpus, independently authored expected facts, explicit mapping to the production support matrices, real-extractor precision/recall and citation validation, repeated-extraction canonical-hash determinism checks, and CI reports for Issue [#94](https://github.com/Second-Origin/PARTHA/issues/94). |
| [Backend README](../apps/backend/README.md) | Backend contributors | Running the backend, the full endpoint surface (including OAuth and the one public write route), configuration, tests. |
| [Frontend README](../apps/frontend/README.md) | Frontend contributors | Running the frontend, structure, commands, tests. |
| [Marketing site README](../apps/marketing/README.md) | Anyone touching the public landing page | The standalone static marketing site: the 1024px split between the authored desktop canvas and the purpose-built mobile layout, the two demo surfaces, Vercel deployment, and its CI job (install / audit / lint / typecheck / build; no automated tests). |
| [Scripts README](../scripts/README.md) | All contributors | What each helper script does. |

## Reading paths

**New contributor** — [README](../README.md) → [CONTRIBUTING](../CONTRIBUTING.md) → [Local development and troubleshooting](DEVELOPMENT.md) → [System Overview](architecture/SYSTEM_OVERVIEW.md) → the README for your area.

**Changing analysis, parsing, or AI grounding** — [Repository Intelligence](architecture/REPOSITORY_INTELLIGENCE.md), first and in full.

## Documentation rules

- Describe what the code does today.
- Never present heuristic or generated output as a guaranteed fact.
- Represent evidence only as precisely as the implementation supports.
- State limitations plainly. An honest gap is more useful than an optimistic claim.
- No placeholder documents.
- Documentation changes in the same pull request as the behaviour it describes.

## Point-in-time records

These are **not** maintained descriptions of current behaviour. Each captures
what was checked on a given date and is left unedited so it stays usable as
evidence. Where the product has since changed, the record says so at the top
rather than being rewritten.

| Record | Date | What it captures |
| --- | --- | --- |
| [Iteration 1 design QA](qa/ITERATION_1_DESIGN_QA.md) | Iteration 1 | One QA pass of the implemented interface against the Iteration 1 Figma reference. The interface has since changed; the record's own header says how. |
| [Iteration 1 engineer feedback](qa/ITERATION_1_ENGINEER_FEEDBACK.md) | Iteration 1 | Setup and validation feedback collected from an engineer working through the repository. |

For current behaviour, read the [README capability registry](../README.md#what-works-today)
and [System Overview](architecture/SYSTEM_OVERVIEW.md) instead of any record above.
