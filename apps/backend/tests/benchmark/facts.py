"""The benchmark fact model and its comparison identity.

A *fact* is the unit the benchmark scores. It uniformly represents the five
``ri.v1`` output kinds — nodes, edges, assertions, observations, and diagnostics
— so that ``expected`` (golden) facts and ``actual`` (extractor-emitted) facts
can be compared with one exact identity.

The comparison identity (:meth:`Fact.key`) is deliberately *semantic and
complete*: it captures fact type, kind, subject/object/predicate, node name and
language, and — for facts that carry evidence — the full, normalized evidence
span set (path + one-based inclusive lines + granularity + extractor). A node
with the right stable key but the wrong name or language therefore does **not**
match; neither does a fact with the right structural identity but the wrong line
span. That is the whole point of a provenance-aware benchmark (RFC-0001 §6.2,
Issue #94).

Identities never include volatile database ids, so the benchmark never compares
unstable primary keys (Issue #94 "Define the comparison identity explicitly").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.intelligence import canonical

FactType = Literal["node", "edge", "assertion", "observation", "diagnostic"]

FACT_TYPES: tuple[FactType, ...] = ("node", "edge", "assertion", "observation", "diagnostic")


@dataclass(frozen=True)
class EvidenceSpan:
    """One normalized citation: a repository-relative span (RFC-0001 §6.1)."""

    path: str
    start_line: int
    end_line: int
    extractor: str
    extractor_version: str
    granularity: str = "span"

    def key(self) -> tuple[Any, ...]:
        return (
            self.path,
            self.start_line,
            self.end_line,
            self.granularity,
            self.extractor,
            self.extractor_version,
        )


def _evidence_set_key(evidence: tuple[EvidenceSpan, ...]) -> tuple[Any, ...]:
    # Order-independent: evidence is a set at the semantic level (RFC §5.4/§12.3),
    # so the identity is the sorted tuple of the individual span keys.
    return tuple(sorted(span.key() for span in evidence))


@dataclass(frozen=True)
class Fact:
    """A single comparable claim.

    Only the fields relevant to a given ``fact_type`` are populated; the
    comparison key uses exactly the fields that make the fact semantically
    distinct, so an incomplete or mis-located fact can never be scored correct.
    """

    fact_type: FactType
    # Structural identity ----------------------------------------------------
    kind: str = ""  # node_kind, edge/observation predicate, or diagnostic code
    subject: str = ""  # stable key / subject, or diagnostic subject
    object: str = ""  # object stable key (edges), or diagnostic object
    predicate: str = ""  # edge/assertion/observation predicate
    name: str = ""  # node display name; empty for non-node facts
    language: str = ""  # node language; empty when absent / not applicable
    referent: str = ""  # observation referent_text
    ordinal: int = 0  # observation identity ordinal; zero when not applicable
    truth_class: str = ""  # observed | resolved | inferred
    value: str = ""  # canonical JCS of an assertion value, when relevant
    severity: str = ""  # diagnostic severity
    category: str = ""  # diagnostic category
    message: str = ""  # deterministic diagnostic message
    producer: str = ""  # diagnostic producer (producer@version)
    # Provenance -------------------------------------------------------------
    evidence: tuple[EvidenceSpan, ...] = ()
    # Bookkeeping (never part of identity) -----------------------------------
    details: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def key(self) -> tuple[Any, ...]:
        """Return the exact, hashable comparison identity of this fact."""

        return (
            self.fact_type,
            self.kind,
            self.subject,
            self.object,
            self.predicate,
            self.name,
            self.language,
            self.referent,
            self.ordinal,
            self.truth_class,
            self.value,
            self.severity,
            self.producer,
            _evidence_set_key(self.evidence),
        )


def canonical_value(value: Any) -> str:
    """Stable string form of an assertion value for the comparison key."""

    return canonical.canonical_json_bytes(value).decode("utf-8")


def normalize_evidence_path(path: str) -> str:
    """Normalize an evidence path with the real RFC-0001 §4.2 normalizer."""

    return canonical.normalize_repo_path(path)
