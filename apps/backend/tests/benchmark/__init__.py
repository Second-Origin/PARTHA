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

The default :mod:`benchmark.adapter` runs the merged Python and TypeScript
extractors through the production source-policy pipeline. Every run therefore
enforces measured precision, recall, golden and real-emission citation validity,
support-matrix parity, and repeated-real-extraction snapshot determinism.
"""
