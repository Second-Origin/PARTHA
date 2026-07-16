"""Repository Intelligence golden benchmark harness (Issue #94).

A deterministic, auditable benchmark that measures the Repository Intelligence
extractors against *independently authored* golden facts: extraction precision
and recall, citation/provenance validity, and snapshot-hash determinism.

This package is **test-only** — it is intentionally outside the ``app`` runtime
package (``pyproject.toml`` ships only ``app*``) so no benchmark abstraction
leaks into the product. It exercises the *real* merged contracts:

- ``app.intelligence.canonical`` — the pure canonical graph hash and identities
  (RFC-0001 §12, §4, §5, §6), and
- ``app.intelligence.snapshot_store`` / ``app.models.snapshot`` — the immutable
  ``ri.v1`` ``SnapshotStore`` (RFC-0001 §11).

Dependency status (see ``README.md`` and the PR description): the syntax-aware
TypeScript/Python extractors and their published support matrices land in
**#89/#90**, which are not merged into ``dev`` yet. Everything here that depends
only on the merged #86 evidence contract and #88 persistence is implemented and
enforced now (fixtures, expected facts, the scorer, provenance validity, and
determinism). Live precision/recall scoring plugs a real extractor into the
:mod:`benchmark.adapter` boundary once #89/#90 merge; until then that stage is
reported as ``deferred`` and is never green-washed into a fabricated perfect
score.
"""
