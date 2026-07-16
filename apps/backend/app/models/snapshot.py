"""Immutable Repository Intelligence snapshot persistence (RFC-0001 §11, #88).

These ORM tables are the normalized, revision-addressed system of record that
replaces the mutable ``repo_metadata['intelligence']`` blob. They store the
complete ``ri.v1`` storage contract: snapshots, nodes, edges, assertions,
observations, evidence, derivation references, and diagnostics.

Integrity that can be expressed as a database invariant is enforced here with
constraints and foreign keys (RFC §11.2, §3.3):

- ``UNIQUE(snapshot_id, stable_key)`` — one node per entity per snapshot;
- a partial unique index giving **at most one** ``repo:root`` node per snapshot;
- composite foreign keys tying every edge endpoint, assertion subject, and
  evidence/derivation parent to a row **in the same snapshot** (no
  cross-snapshot or cross-repository leakage);
- deterministic ``edge_id`` / ``assertion_id`` / ``observation_id`` uniqueness
  per snapshot;
- a partial unique index giving **at most one** ``completed`` snapshot per
  complete semantic identity ``(repository_id, revision_value, schema_version,
  producer_set_hash, config_hash)``.

Graph-shape invariants that cannot be a single SQL constraint (derivation
target resolution, acyclicity, provenance completeness, canonical ordering) are
enforced in the sealing transaction (:mod:`app.intelligence.snapshot_store`),
and completed-snapshot immutability is enforced at the persistence boundary by a
``before_flush`` guard in the same module.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import DateTime
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.repository import _hex_only_sql

def _utcnow() -> datetime:
    return datetime.now(UTC)


class RiSnapshot(Base):
    __tablename__ = "ri_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(36), nullable=False)
    revision_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    revision_value: Mapped[str] = mapped_column(String(80), nullable=False)
    revision_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    producer_version_set: Mapped[list] = mapped_column(MutableList.as_mutable(JSON), nullable=False)
    producer_set_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="building")
    canonical_graph_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    actual_producers: Mapped[list | None] = mapped_column(MutableList.as_mutable(JSON), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "state IN ('building', 'completed', 'failed')",
            name="ck_ri_snapshots_state",
        ),
        CheckConstraint(
            "revision_kind IN ('git', 'upload')",
            name="ck_ri_snapshots_revision_kind",
        ),
        CheckConstraint(
            "revision_kind <> 'upload' OR "
            f"(revision_ref IS NULL AND length(revision_value) = 71 AND "
            f"substr(revision_value, 1, 7) = 'sha256:' AND {_hex_only_sql('substr(revision_value, 8)')})",
            name="ck_ri_snapshots_upload_revision",
        ),
        CheckConstraint(
            "revision_kind <> 'git' OR "
            f"(length(revision_value) = 40 AND {_hex_only_sql('revision_value')} AND "
            "(revision_ref IS NULL OR revision_ref LIKE 'refs/%'))",
            name="ck_ri_snapshots_git_revision",
        ),
        CheckConstraint(
            f"length(producer_set_hash) = 71 AND substr(producer_set_hash, 1, 7) = 'sha256:' AND "
            f"{_hex_only_sql('substr(producer_set_hash, 8)')}",
            name="ck_ri_snapshots_producer_hash",
        ),
        CheckConstraint(
            f"length(config_hash) = 71 AND substr(config_hash, 1, 7) = 'sha256:' AND "
            f"{_hex_only_sql('substr(config_hash, 8)')}",
            name="ck_ri_snapshots_config_hash",
        ),
        CheckConstraint(
            "(state = 'completed' AND canonical_graph_hash IS NOT NULL AND sealed_at IS NOT NULL) OR "
            "(state <> 'completed' AND canonical_graph_hash IS NULL AND sealed_at IS NULL)",
            name="ck_ri_snapshots_seal_fields",
        ),
        CheckConstraint(
            "canonical_graph_hash IS NULL OR "
            f"(length(canonical_graph_hash) = 71 AND substr(canonical_graph_hash, 1, 7) = 'sha256:' AND "
            f"{_hex_only_sql('substr(canonical_graph_hash, 8)')})",
            name="ck_ri_snapshots_canonical_hash",
        ),
        ForeignKeyConstraint(
            ["repository_id", "revision_kind", "revision_value"],
            ["repositories.id", "repositories.revision_kind", "repositories.revision_value"],
            name="fk_ri_snapshots_repository_revision",
            ondelete="CASCADE",
        ),
        Index("ix_ri_snapshots_repository_id", "repository_id"),
        Index("ix_ri_snapshots_repository_revision", "repository_id", "revision_value"),
        # At most one completed snapshot per complete semantic identity (RFC §3.3).
        Index(
            "uq_ri_snapshots_completed_identity",
            "repository_id",
            "revision_value",
            "schema_version",
            "producer_set_hash",
            "config_hash",
            unique=True,
            sqlite_where=text("state = 'completed'"),
            postgresql_where=text("state = 'completed'"),
        ),
    )


class RiNode(Base):
    __tablename__ = "ri_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(48), ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    stable_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    node_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    truth_class: Mapped[str] = mapped_column(String(16), nullable=False, default="observed")
    properties: Mapped[dict | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "stable_key", name="uq_ri_nodes_snapshot_stable_key"),
        # Target for same-snapshot composite foreign keys from edges/evidence.
        UniqueConstraint("snapshot_id", "id", name="uq_ri_nodes_snapshot_row"),
        CheckConstraint("truth_class = 'observed'", name="ck_ri_nodes_truth_class"),
        Index("ix_ri_nodes_snapshot_id", "snapshot_id"),
        # Exactly one repository (repo:root) node per snapshot: the DB enforces
        # "at most one"; the sealing transaction enforces "at least one".
        Index(
            "uq_ri_nodes_single_root",
            "snapshot_id",
            unique=True,
            sqlite_where=text("node_kind = 'repository'"),
            postgresql_where=text("node_kind = 'repository'"),
        ),
    )


class RiEdge(Base):
    __tablename__ = "ri_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(48), ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    edge_id: Mapped[str] = mapped_column(String(96), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    predicate: Mapped[str] = mapped_column(String(32), nullable=False)
    object_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    truth_class: Mapped[str] = mapped_column(String(16), nullable=False, default="resolved")
    producer: Mapped[str] = mapped_column(String(128), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "edge_id", name="uq_ri_edges_snapshot_edge_id"),
        UniqueConstraint(
            "snapshot_id",
            "subject_key",
            "predicate",
            "object_key",
            name="uq_ri_edges_snapshot_triple",
        ),
        UniqueConstraint("snapshot_id", "id", name="uq_ri_edges_snapshot_row"),
        CheckConstraint("truth_class = 'resolved'", name="ck_ri_edges_truth_class"),
        # Valid, same-snapshot endpoints (RFC §5.2): both endpoints must be a
        # node in this snapshot. Composite keys carry snapshot_id so an endpoint
        # can never resolve into a different snapshot.
        ForeignKeyConstraint(
            ["snapshot_id", "subject_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_edges_subject_node",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "object_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_edges_object_node",
            ondelete="CASCADE",
        ),
        Index("ix_ri_edges_snapshot_id", "snapshot_id"),
    )


class RiAssertion(Base):
    __tablename__ = "ri_assertions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(48), ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    assertion_id: Mapped[str] = mapped_column(String(96), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    predicate: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False)
    truth_class: Mapped[str] = mapped_column(String(16), nullable=False, default="inferred")
    producer: Mapped[str] = mapped_column(String(128), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "assertion_id", name="uq_ri_assertions_snapshot_assertion_id"),
        UniqueConstraint("snapshot_id", "id", name="uq_ri_assertions_snapshot_row"),
        CheckConstraint("truth_class = 'inferred'", name="ck_ri_assertions_truth_class"),
        # An assertion subject must resolve to an existing node in the same
        # snapshot (RFC §5.6).
        ForeignKeyConstraint(
            ["snapshot_id", "subject_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_assertions_subject_node",
            ondelete="CASCADE",
        ),
        Index("ix_ri_assertions_snapshot_id", "snapshot_id"),
    )


class RiObservation(Base):
    __tablename__ = "ri_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(48), ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    observation_id: Mapped[str] = mapped_column(String(96), nullable=False)
    observed_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    referent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "observation_id", name="uq_ri_observations_snapshot_obs_id"),
        UniqueConstraint("snapshot_id", "id", name="uq_ri_observations_snapshot_row"),
        CheckConstraint("ordinal >= 1", name="ck_ri_observations_ordinal"),
        ForeignKeyConstraint(
            ["snapshot_id", "subject_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_observations_subject_node",
            ondelete="CASCADE",
        ),
        Index("ix_ri_observations_snapshot_id", "snapshot_id"),
    )


class RiEvidence(Base):
    __tablename__ = "ri_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(48), ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    node_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edge_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observation_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    granularity: Mapped[str] = mapped_column(String(16), nullable=False, default="span")
    extractor: Mapped[str] = mapped_column(String(128), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        # Exactly one parent fact (node, edge, or observation).
        CheckConstraint(
            "(CASE WHEN node_ref IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN edge_ref IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN observation_ref IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_ri_evidence_single_parent",
        ),
        CheckConstraint("start_line >= 1 AND end_line >= start_line", name="ck_ri_evidence_span"),
        CheckConstraint("granularity IN ('span', 'file')", name="ck_ri_evidence_granularity"),
        # Defence in depth against absolute paths and traversal; full RFC §4.2
        # normalization/rejection happens in the persistence layer before insert.
        CheckConstraint("path NOT LIKE '/%'", name="ck_ri_evidence_relative_path"),
        # Same-snapshot provenance (RFC §6, §13): a NULL ref column disables its
        # composite FK, so exactly the one populated parent link is enforced.
        ForeignKeyConstraint(
            ["snapshot_id", "node_ref"],
            ["ri_nodes.snapshot_id", "ri_nodes.id"],
            name="fk_ri_evidence_node",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "edge_ref"],
            ["ri_edges.snapshot_id", "ri_edges.id"],
            name="fk_ri_evidence_edge",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "observation_ref"],
            ["ri_observations.snapshot_id", "ri_observations.id"],
            name="fk_ri_evidence_observation",
            ondelete="CASCADE",
        ),
        Index("ix_ri_evidence_snapshot_id", "snapshot_id"),
        Index("ix_ri_evidence_node_ref", "snapshot_id", "node_ref"),
        Index("ix_ri_evidence_edge_ref", "snapshot_id", "edge_ref"),
        Index("ix_ri_evidence_observation_ref", "snapshot_id", "observation_ref"),
        Index(
            "uq_ri_evidence_node_fact",
            "snapshot_id",
            "node_ref",
            "path",
            "start_line",
            "end_line",
            "granularity",
            "extractor",
            "extractor_version",
            unique=True,
            sqlite_where=text("node_ref IS NOT NULL"),
            postgresql_where=text("node_ref IS NOT NULL"),
        ),
        Index(
            "uq_ri_evidence_edge_fact",
            "snapshot_id",
            "edge_ref",
            "path",
            "start_line",
            "end_line",
            "granularity",
            "extractor",
            "extractor_version",
            unique=True,
            sqlite_where=text("edge_ref IS NOT NULL"),
            postgresql_where=text("edge_ref IS NOT NULL"),
        ),
        Index(
            "uq_ri_evidence_observation_fact",
            "snapshot_id",
            "observation_ref",
            "path",
            "start_line",
            "end_line",
            "granularity",
            "extractor",
            "extractor_version",
            unique=True,
            sqlite_where=text("observation_ref IS NOT NULL"),
            postgresql_where=text("observation_ref IS NOT NULL"),
        ),
    )


class RiDerivation(Base):
    __tablename__ = "ri_derivations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(48), ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    edge_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assertion_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ref_identity: Mapped[str] = mapped_column(String(1024), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN edge_ref IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN assertion_ref IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_ri_derivations_single_parent",
        ),
        CheckConstraint(
            "ref_kind IN ('observation', 'node', 'edge', 'assertion')",
            name="ck_ri_derivations_ref_kind",
        ),
        # The derived fact (edge or assertion) must live in the same snapshot.
        # The referenced *target* is resolved (and cycle-checked) in the sealing
        # transaction because it can point at four different fact tables by
        # content identity, not a single-column primary key (RFC §11.2 rule 7).
        ForeignKeyConstraint(
            ["snapshot_id", "edge_ref"],
            ["ri_edges.snapshot_id", "ri_edges.id"],
            name="fk_ri_derivations_edge",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "assertion_ref"],
            ["ri_assertions.snapshot_id", "ri_assertions.id"],
            name="fk_ri_derivations_assertion",
            ondelete="CASCADE",
        ),
        Index("ix_ri_derivations_snapshot_id", "snapshot_id"),
        Index(
            "uq_ri_derivations_edge_fact",
            "snapshot_id",
            "edge_ref",
            "ref_kind",
            "ref_identity",
            unique=True,
            sqlite_where=text("edge_ref IS NOT NULL"),
            postgresql_where=text("edge_ref IS NOT NULL"),
        ),
        Index(
            "uq_ri_derivations_assertion_fact",
            "snapshot_id",
            "assertion_ref",
            "ref_kind",
            "ref_identity",
            unique=True,
            sqlite_where=text("assertion_ref IS NOT NULL"),
            postgresql_where=text("assertion_ref IS NOT NULL"),
        ),
    )


class RiDiagnostic(Base):
    __tablename__ = "ri_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(48), ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    span_start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    span_end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    producer: Mapped[str] = mapped_column(String(160), nullable=False)
    subject_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    details: Mapped[dict | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "severity IN ('fatal', 'error', 'warning', 'info')",
            name="ck_ri_diagnostics_severity",
        ),
        CheckConstraint(
            "(span_start_line IS NULL AND span_end_line IS NULL) OR "
            "(span_start_line >= 1 AND span_end_line >= span_start_line)",
            name="ck_ri_diagnostics_span",
        ),
        CheckConstraint("path IS NULL OR path NOT LIKE '/%'", name="ck_ri_diagnostics_relative_path"),
        Index("ix_ri_diagnostics_snapshot_id", "snapshot_id"),
    )
