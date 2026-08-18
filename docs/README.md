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
| [SECURITY](../SECURITY.md) | Anyone reporting a vulnerability | How to disclose privately. Never open a public issue for a vulnerability. |
| [AI provider egress policy](security/AI_PROVIDER_EGRESS.md) | Operators and backend contributors | Deployment-owned provider destination policy, DNS pinning, redirect handling, safe defaults, and required production network controls. |
| [WCAG 2.2 AA accessibility baseline](accessibility/WCAG_2_2_AA_BASELINE.md) | Frontend contributors and accessibility reviewers | Reproducible automated coverage for the Phase 0 journeys, the outstanding human verification checklist, confirmed findings, and linked follow-up issues. |
| [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) | Everyone | Expected conduct and how to report a violation. |
| [System Overview](architecture/SYSTEM_OVERVIEW.md) | Contributors and maintainers | Current components, ingestion flow, persistence, consumers, trust boundaries, and architectural limitations. |
| [Repository Intelligence](architecture/REPOSITORY_INTELLIGENCE.md) | Anyone changing analysis behaviour | What is extracted, what is deterministic versus heuristic, how facts are persisted, who consumes them, what consumers must not do, and where evidence and provenance stop. **Read this before touching analysis.** |
| [Repository Intelligence v1 RFC](architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md) | Contributors on the intelligence track | **Accepted** architectural contract (RFC-0001, tracking [#86](https://github.com/Second-Origin/PARTHA/issues/86)) for the snapshot/evidence schema: deterministic entity keys, separate inferred assertions, complete derivation chains, producer identity and producer-version tracking, provenance, immutability, diagnostics, versioning, and total canonical graph hashing. **Status: Accepted** — independently approved by [@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24) on [Issue #86](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780) and [PR #101](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647) on 2026-07-16. The durable snapshot pipeline and product-consumer migration are implemented; §17 tracks the remaining contract gaps. |
| [Repository Intelligence relationship resolution](architecture/REPOSITORY_INTELLIGENCE_RESOLUTION.md) | Contributors changing extraction or resolution | The deterministic resolver (Issue [#91](https://github.com/Second-Origin/PARTHA/issues/91)): how stored observations become `resolved` edges, the one/zero/many candidate outcomes, and the `RI-RES-UNRESOLVED` / `RI-RES-AMBIGUOUS` diagnostics emitted instead of a guess. |
| [Repository Lineage RFC](architecture/REPOSITORY_LINEAGE_RFC.md) | Contributors on the intelligence track | **Design only** (RFC-0002, tracking [#298](https://github.com/Second-Origin/PARTHA/issues/298)) for grouping successive imports of the same repository into a durable lineage identity. **Status: Accepted by owner decision; independent ratification was waived on 2026-08-11.** Implementation is authorized in principle but has not started and requires migration, backfill, and concurrency planning first. The design itself creates no table, column, service, or surface. Revision identity itself is unchanged and still governed by RFC-0001 §3. |
| [Repository Intelligence golden benchmark](../apps/backend/tests/benchmark/README.md) | Contributors on the intelligence track | The versioned golden fixture corpus, independently authored expected facts, explicit mapping to the production support matrices, real-extractor precision/recall and citation validation, repeated-extraction canonical-hash determinism checks, and CI reports for Issue [#94](https://github.com/Second-Origin/PARTHA/issues/94). |
| [Backend README](../apps/backend/README.md) | Backend contributors | Running the backend, endpoints, configuration, tests. |
| [Frontend README](../apps/frontend/README.md) | Frontend contributors | Running the frontend, structure, commands, tests. |
| [Scripts README](../scripts/README.md) | All contributors | What each helper script does. |

## Reading paths

**New contributor** — [README](../README.md) → [CONTRIBUTING](../CONTRIBUTING.md) → [System Overview](architecture/SYSTEM_OVERVIEW.md) → the README for your area.

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

- Internal point-in-time QA notes are preserved in the repository but are not maintained contributor documentation.
