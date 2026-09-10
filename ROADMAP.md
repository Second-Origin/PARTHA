# PARTHA Roadmap

This roadmap communicates **direction, not delivery guarantees**. It has no dates. Items
move between sections, get re-scoped, or get dropped as the work and the product's needs
become clearer. For what exists today, read the [capability matrix](docs/CAPABILITIES.md);
for accepted design contracts, read the [RFCs](docs/architecture/).

PARTHA is being built toward a private, versioned intelligence layer for software
repositories: something that helps people understand unfamiliar code faster and gives AI a
trusted, governed context instead of re-reading the whole codebase on every question. The
sealed per-revision snapshot is the foundation for that; most of what follows is about
making the model stay current and comparable over time.

## Current focus

- **Truth over breadth.** Every capability the product exposes is backed by the generated
  registry and the golden benchmark, and documentation is not allowed to drift ahead of the
  code. Widening extractor coverage happens behind that gate, not ahead of it.
- **Reliability of the core workflow.** Import → analyse → seal → query has to be
  dependable end to end before history and comparison features are built on top of it.

## Next

- **Repository refresh.** A product workflow to re-analyse a lineage's current revision and
  seal a new snapshot without a manual re-import — the first step toward the model staying
  current as a codebase evolves.
- **Cross-revision entity correspondence.** Matching an entity in one snapshot to its
  counterpart in another (see [RFC-0001 §4.1](docs/architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md#41-principle-and-cross-revision-guarantees)
  for why stable keys alone are not enough). This is the prerequisite for everything in the
  "Later" section, and is the subject of a planned RFC — **not yet designed or built**.

## Later

Each of these depends on cross-revision correspondence landing first:

- **Structural graph delta** — a classified `Snapshot A ↔ Snapshot B` diff
  (`ADDED` / `REMOVED` / `MODIFIED` / `MOVED` / `RENAMED` / …).
- **Architecture evolution** — how modules, layers, and relationships changed across a
  lineage.
- **Change-aware impact analysis** — a blast radius computed from an actual delta between
  two revisions, rather than reachability inside one snapshot.
- **Incremental indexing** — analysing only what changed instead of the whole repository.

## Explicitly out of scope / not claimed today

These are stated plainly so the rest of the documentation can stay concise:

- **No generic two-revision structural graph comparison.** Repository Lineage preserves
  revision *history*; it does not diff snapshots. See
  [RFC-0002 §1.3](docs/architecture/REPOSITORY_LINEAGE_RFC.md#13-implementation-status).
- **No guaranteed rename or move identity recovery** across arbitrary refactors.
- **No exact historical blast radius.** The current impact query is single-snapshot
  structural reachability, not a change delta.
- **No universal language coverage.** Deep extraction is Python and TypeScript/JavaScript;
  other languages get file inventory and metadata.
- **No vulnerability or outdated-dependency scanner.** Dependency and Review responses
  report explicit not-computed / not-assessed states.
- **No assumption that configured AI is local.** Provider-backed AI can be external
  depending on configuration; the [egress policy](docs/security/AI_PROVIDER_EGRESS.md)
  governs where it may go.
- **No hosted or multi-tenant service.** PARTHA is self-hosted; broad production hardening
  is not in scope for now.

## Proposing a change

Roadmap direction is set by the maintainers (see [GOVERNANCE.md](GOVERNANCE.md)). Larger
architectural items go through the RFC process before they are built. To suggest something,
open a GitHub issue describing the problem — not just the feature — and, for anything that
would change an architectural contract, expect it to become an RFC.
