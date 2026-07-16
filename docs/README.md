# PARTHA Documentation

Every document listed here is maintained and describes the system as it currently exists.

**Current behaviour belongs in documentation. Future work belongs in GitHub issues.** If you find a claim the code does not support, that is a bug — please open an issue.

## Index

| Document | Reader | Purpose |
| --- | --- | --- |
| [README](../README.md) | Anyone evaluating or running PARTHA | What PARTHA is, what currently works, how to run it locally, and its limitations. |
| [CONTRIBUTING](../CONTRIBUTING.md) | Contributors | The contribution rules: fork-first workflow, claiming an issue, branch naming, rebasing, pull requests, Definition of Ready and Done. Read before opening a PR. |
| [SECURITY](../SECURITY.md) | Anyone reporting a vulnerability | How to disclose privately. Never open a public issue for a vulnerability. |
| [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) | Everyone | Expected conduct and how to report a violation. |
| [System Overview](architecture/SYSTEM_OVERVIEW.md) | Contributors and maintainers | Current components, ingestion flow, persistence, consumers, trust boundaries, and architectural limitations. |
| [Repository Intelligence](architecture/REPOSITORY_INTELLIGENCE.md) | Anyone changing analysis behaviour | What is extracted, what is deterministic versus heuristic, how facts are persisted, who consumes them, what consumers must not do, and where evidence and provenance stop. **Read this before touching analysis.** |
| [Repository Intelligence v1 RFC](architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md) | Contributors on the intelligence track | **Accepted** architectural contract (RFC-0001, tracking [#86](https://github.com/Second-Origin/PARTHA/issues/86)) for the snapshot/evidence schema: deterministic entity keys, separate inferred assertions, complete derivation chains, planned producer identity, provenance, immutability, diagnostics, versioning, and total canonical graph hashing. **Status: Accepted** — independently approved by [@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24) on [Issue #86](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780) and [PR #101](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647) on 2026-07-16. Acceptance records the governing contract; it does not make unimplemented downstream functionality current product behaviour. §17 tracks implementation status. Governs downstream issues #87–#95. |
| [Backend README](../apps/backend/README.md) | Backend contributors | Running the backend, endpoints, configuration, tests. |
| [Frontend README](../apps/frontend/README.md) | Frontend contributors | Running the frontend, structure, commands, tests. |
| [Scripts README](../scripts/README.md) | All contributors | What each helper script does. |
| [Packages README](../packages/README.md) | All contributors | The shared-packages directory. |

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
