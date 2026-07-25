"""Declared provenance for repository-derived responses.

PARTHA currently has two intelligence paths: the sealed, evidence-backed
``ri.v1`` snapshot model, and the older ``RepositoryIntelligenceEngine``
heuristic that reads the mutable ``repo_metadata['intelligence']`` blob.

A surface must never let a user assume snapshot-grade provenance when the value
was produced by the legacy path. Responses therefore declare which path built
them, and legacy responses carry a plain-language limitation the frontend
renders next to the data.
"""

from typing import Literal

from app.schemas.base import CamelModel

IntelligenceSource = Literal["ri.v1", "legacy-heuristic"]

LEGACY_LIMITATION = (
    "Derived from declared manifests by the legacy analysis engine, not from a "
    "sealed evidence snapshot. Results are not bound to a verifiable revision "
    "manifest and may differ from snapshot-backed surfaces."
)


class IntelligenceProvenance(CamelModel):
    """Which intelligence path produced a repository-derived response."""

    source: IntelligenceSource
    #: Plain-language limitation shown to users. Required for legacy sources so
    #: a heuristic result can never be presented as snapshot-backed evidence.
    limitation: str | None = None

    @classmethod
    def snapshot(cls) -> "IntelligenceProvenance":
        return cls(source="ri.v1", limitation=None)

    @classmethod
    def legacy(cls, limitation: str = LEGACY_LIMITATION) -> "IntelligenceProvenance":
        return cls(source="legacy-heuristic", limitation=limitation)
