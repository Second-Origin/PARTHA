"""add revision identity and immutable intelligence snapshots

Revision ID: 0005_revision_snapshots
Revises: 0004_ai_provider_configs
Create Date: 2026-07-16

This migration implements issues #87 and #88 as one revision-keyed persistence
boundary. It transforms exact legacy ``repo_metadata['commitSha']`` values into
typed repository columns but deliberately does not copy legacy regex
``repo_metadata['intelligence']`` facts into ``ri.v1`` tables: those facts lack
RFC-valid spans and producer provenance.

Downgrade drops all snapshot data created under this revision, while preserving
every repository column and JSON value that existed before the upgrade.
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa

revision = "0005_revision_snapshots"
down_revision = "0004_ai_provider_configs"
branch_labels = None
depends_on = None

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_UPLOAD_SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_BODY_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def _hex_only_sql(expression: str) -> str:
    for character in "0123456789abcdef":
        expression = f"replace({expression}, '{character}', '')"
    return f"{expression} = ''"


def _resolved_ref(branch: object) -> str | None:
    """Derive a ref only from deterministic, explicit legacy branch metadata."""

    if not isinstance(branch, str) or not branch:
        return None
    if branch.startswith(("refs/heads/", "refs/tags/")):
        body = branch.split("/", 2)[2]
        return branch if _REF_BODY_RE.fullmatch(body) and ".." not in body else None
    if (
        not _REF_BODY_RE.fullmatch(branch)
        or branch.startswith(("/", "-"))
        or branch.endswith(("/", "."))
        or ".." in branch
    ):
        return None
    return f"refs/heads/{branch}"


def _add_repository_revision_columns() -> None:
    with op.batch_alter_table("repositories") as batch:
        batch.add_column(sa.Column("revision_kind", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("revision_value", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("revision_ref", sa.String(length=255), nullable=True))
        batch.create_unique_constraint(
            "uq_repositories_id_revision",
            ["id", "revision_kind", "revision_value"],
        )
        batch.create_check_constraint(
            "ck_repositories_revision_kind",
            "revision_kind IS NULL OR revision_kind IN ('git', 'upload')",
        )
        batch.create_check_constraint(
            "ck_repositories_revision_complete",
            "(revision_kind IS NULL AND revision_value IS NULL AND revision_ref IS NULL) OR "
            "(revision_kind IS NOT NULL AND revision_value IS NOT NULL)",
        )
        batch.create_check_constraint(
            "ck_repositories_upload_revision",
            "revision_kind <> 'upload' OR "
            f"(revision_ref IS NULL AND length(revision_value) = 71 AND "
            f"substr(revision_value, 1, 7) = 'sha256:' AND {_hex_only_sql('substr(revision_value, 8)')})",
        )
        batch.create_check_constraint(
            "ck_repositories_git_revision",
            "revision_kind <> 'git' OR "
            f"(length(revision_value) = 40 AND {_hex_only_sql('revision_value')} AND "
            "(revision_ref IS NULL OR revision_ref LIKE 'refs/%'))",
        )
        batch.create_index("ix_repositories_revision_value", ["revision_value"], unique=False)


def _backfill_repository_revisions() -> None:
    connection = op.get_bind()
    repositories = sa.table(
        "repositories",
        sa.column("id", sa.String()),
        sa.column("branch", sa.String()),
        sa.column("repo_metadata", sa.JSON()),
        sa.column("revision_kind", sa.String()),
        sa.column("revision_value", sa.String()),
        sa.column("revision_ref", sa.String()),
    )
    rows = connection.execute(
        sa.select(repositories.c.id, repositories.c.branch, repositories.c.repo_metadata)
    ).mappings()
    for row in rows:
        metadata = row["repo_metadata"]
        legacy_value = metadata.get("commitSha") if isinstance(metadata, dict) else None
        values: dict[str, object]
        if isinstance(legacy_value, str) and _UPLOAD_SHA_RE.fullmatch(legacy_value):
            values = {"revision_kind": "upload", "revision_value": legacy_value, "revision_ref": None}
        elif isinstance(legacy_value, str) and _GIT_SHA_RE.fullmatch(legacy_value):
            values = {
                "revision_kind": "git",
                "revision_value": legacy_value,
                "revision_ref": _resolved_ref(row["branch"]),
            }
        else:
            # Invalid or absent legacy values remain explicitly unidentified.
            # No SHA or ref is fabricated from a URL, filename, timestamp, or
            # current working tree.
            values = {"revision_kind": None, "revision_value": None, "revision_ref": None}
        connection.execute(
            repositories.update().where(repositories.c.id == row["id"]).values(**values)
        )


def _create_snapshot_tables() -> None:
    op.create_table(
        "ri_snapshots",
        sa.Column("snapshot_id", sa.String(length=48), primary_key=True),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("revision_kind", sa.String(length=16), nullable=False),
        sa.Column("revision_value", sa.String(length=80), nullable=False),
        sa.Column("revision_ref", sa.String(length=255), nullable=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("producer_version_set", sa.JSON(), nullable=False),
        sa.Column("producer_set_hash", sa.String(length=80), nullable=False),
        sa.Column("config_hash", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("canonical_graph_hash", sa.String(length=80), nullable=True),
        sa.Column("actual_producers", sa.JSON(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("state IN ('building', 'completed', 'failed')", name="ck_ri_snapshots_state"),
        sa.CheckConstraint("revision_kind IN ('git', 'upload')", name="ck_ri_snapshots_revision_kind"),
        sa.CheckConstraint(
            "revision_kind <> 'upload' OR "
            f"(revision_ref IS NULL AND length(revision_value) = 71 AND "
            f"substr(revision_value, 1, 7) = 'sha256:' AND {_hex_only_sql('substr(revision_value, 8)')})",
            name="ck_ri_snapshots_upload_revision",
        ),
        sa.CheckConstraint(
            "revision_kind <> 'git' OR "
            f"(length(revision_value) = 40 AND {_hex_only_sql('revision_value')} AND "
            "(revision_ref IS NULL OR revision_ref LIKE 'refs/%'))",
            name="ck_ri_snapshots_git_revision",
        ),
        sa.CheckConstraint(
            f"length(producer_set_hash) = 71 AND substr(producer_set_hash, 1, 7) = 'sha256:' AND "
            f"{_hex_only_sql('substr(producer_set_hash, 8)')}",
            name="ck_ri_snapshots_producer_hash",
        ),
        sa.CheckConstraint(
            f"length(config_hash) = 71 AND substr(config_hash, 1, 7) = 'sha256:' AND "
            f"{_hex_only_sql('substr(config_hash, 8)')}",
            name="ck_ri_snapshots_config_hash",
        ),
        sa.CheckConstraint(
            "(state = 'completed' AND canonical_graph_hash IS NOT NULL AND sealed_at IS NOT NULL) OR "
            "(state <> 'completed' AND canonical_graph_hash IS NULL AND sealed_at IS NULL)",
            name="ck_ri_snapshots_seal_fields",
        ),
        sa.CheckConstraint(
            "canonical_graph_hash IS NULL OR "
            f"(length(canonical_graph_hash) = 71 AND substr(canonical_graph_hash, 1, 7) = 'sha256:' AND "
            f"{_hex_only_sql('substr(canonical_graph_hash, 8)')})",
            name="ck_ri_snapshots_canonical_hash",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id", "revision_kind", "revision_value"],
            ["repositories.id", "repositories.revision_kind", "repositories.revision_value"],
            name="fk_ri_snapshots_repository_revision",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ri_snapshots_repository_id", "ri_snapshots", ["repository_id"])
    op.create_index(
        "ix_ri_snapshots_repository_revision",
        "ri_snapshots",
        ["repository_id", "revision_value"],
    )
    op.create_index(
        "uq_ri_snapshots_completed_identity",
        "ri_snapshots",
        ["repository_id", "revision_value", "schema_version", "producer_set_hash", "config_hash"],
        unique=True,
        sqlite_where=sa.text("state = 'completed'"),
        postgresql_where=sa.text("state = 'completed'"),
    )

    op.create_table(
        "ri_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=48),
            sa.ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stable_key", sa.String(length=1024), nullable=False),
        sa.Column("node_kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("truth_class", sa.String(length=16), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=True),
        sa.UniqueConstraint("snapshot_id", "stable_key", name="uq_ri_nodes_snapshot_stable_key"),
        sa.UniqueConstraint("snapshot_id", "id", name="uq_ri_nodes_snapshot_row"),
        sa.CheckConstraint("truth_class = 'observed'", name="ck_ri_nodes_truth_class"),
    )
    op.create_index("ix_ri_nodes_snapshot_id", "ri_nodes", ["snapshot_id"])
    op.create_index(
        "uq_ri_nodes_single_root",
        "ri_nodes",
        ["snapshot_id"],
        unique=True,
        sqlite_where=sa.text("node_kind = 'repository'"),
        postgresql_where=sa.text("node_kind = 'repository'"),
    )

    op.create_table(
        "ri_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=48),
            sa.ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_id", sa.String(length=96), nullable=False),
        sa.Column("subject_kind", sa.String(length=16), nullable=False),
        sa.Column("subject_key", sa.String(length=1024), nullable=False),
        sa.Column("predicate", sa.String(length=32), nullable=False),
        sa.Column("object_kind", sa.String(length=16), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("truth_class", sa.String(length=16), nullable=False),
        sa.Column("producer", sa.String(length=128), nullable=False),
        sa.Column("producer_version", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("snapshot_id", "edge_id", name="uq_ri_edges_snapshot_edge_id"),
        sa.UniqueConstraint(
            "snapshot_id", "subject_key", "predicate", "object_key", name="uq_ri_edges_snapshot_triple"
        ),
        sa.UniqueConstraint("snapshot_id", "id", name="uq_ri_edges_snapshot_row"),
        sa.CheckConstraint("truth_class = 'resolved'", name="ck_ri_edges_truth_class"),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "subject_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_edges_subject_node",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "object_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_edges_object_node",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ri_edges_snapshot_id", "ri_edges", ["snapshot_id"])

    op.create_table(
        "ri_assertions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=48),
            sa.ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assertion_id", sa.String(length=96), nullable=False),
        sa.Column("subject_kind", sa.String(length=16), nullable=False),
        sa.Column("subject_key", sa.String(length=1024), nullable=False),
        sa.Column("predicate", sa.String(length=32), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("truth_class", sa.String(length=16), nullable=False),
        sa.Column("producer", sa.String(length=128), nullable=False),
        sa.Column("producer_version", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("snapshot_id", "assertion_id", name="uq_ri_assertions_snapshot_assertion_id"),
        sa.UniqueConstraint("snapshot_id", "id", name="uq_ri_assertions_snapshot_row"),
        sa.CheckConstraint("truth_class = 'inferred'", name="ck_ri_assertions_truth_class"),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "subject_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_assertions_subject_node",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ri_assertions_snapshot_id", "ri_assertions", ["snapshot_id"])

    op.create_table(
        "ri_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=48),
            sa.ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("observation_id", sa.String(length=96), nullable=False),
        sa.Column("observed_kind", sa.String(length=16), nullable=False),
        sa.Column("subject_kind", sa.String(length=16), nullable=False),
        sa.Column("subject_key", sa.String(length=1024), nullable=False),
        sa.Column("referent_text", sa.Text(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("snapshot_id", "observation_id", name="uq_ri_observations_snapshot_obs_id"),
        sa.UniqueConstraint("snapshot_id", "id", name="uq_ri_observations_snapshot_row"),
        sa.CheckConstraint("ordinal >= 1", name="ck_ri_observations_ordinal"),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "subject_key"],
            ["ri_nodes.snapshot_id", "ri_nodes.stable_key"],
            name="fk_ri_observations_subject_node",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ri_observations_snapshot_id", "ri_observations", ["snapshot_id"])

    op.create_table(
        "ri_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=48),
            sa.ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_ref", sa.Integer(), nullable=True),
        sa.Column("edge_ref", sa.Integer(), nullable=True),
        sa.Column("observation_ref", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("logical_line_count", sa.Integer(), nullable=False),
        sa.Column("granularity", sa.String(length=16), nullable=False),
        sa.Column("extractor", sa.String(length=128), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN node_ref IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN edge_ref IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN observation_ref IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_ri_evidence_single_parent",
        ),
        sa.CheckConstraint(
            "start_line >= 1 AND end_line >= start_line AND "
            "logical_line_count >= 1 AND end_line <= logical_line_count",
            name="ck_ri_evidence_span",
        ),
        sa.CheckConstraint("granularity IN ('span', 'file')", name="ck_ri_evidence_granularity"),
        sa.CheckConstraint("path NOT LIKE '/%'", name="ck_ri_evidence_relative_path"),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "node_ref"],
            ["ri_nodes.snapshot_id", "ri_nodes.id"],
            name="fk_ri_evidence_node",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "edge_ref"],
            ["ri_edges.snapshot_id", "ri_edges.id"],
            name="fk_ri_evidence_edge",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "observation_ref"],
            ["ri_observations.snapshot_id", "ri_observations.id"],
            name="fk_ri_evidence_observation",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ri_evidence_snapshot_id", "ri_evidence", ["snapshot_id"])
    op.create_index("ix_ri_evidence_node_ref", "ri_evidence", ["snapshot_id", "node_ref"])
    op.create_index("ix_ri_evidence_edge_ref", "ri_evidence", ["snapshot_id", "edge_ref"])
    op.create_index("ix_ri_evidence_observation_ref", "ri_evidence", ["snapshot_id", "observation_ref"])
    evidence_fields = ["path", "start_line", "end_line", "granularity", "extractor", "extractor_version"]
    for parent in ("node", "edge", "observation"):
        op.create_index(
            f"uq_ri_evidence_{parent}_fact",
            "ri_evidence",
            ["snapshot_id", f"{parent}_ref", *evidence_fields],
            unique=True,
            sqlite_where=sa.text(f"{parent}_ref IS NOT NULL"),
            postgresql_where=sa.text(f"{parent}_ref IS NOT NULL"),
        )

    op.create_table(
        "ri_derivations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=48),
            sa.ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_ref", sa.Integer(), nullable=True),
        sa.Column("assertion_ref", sa.Integer(), nullable=True),
        sa.Column("ref_kind", sa.String(length=16), nullable=False),
        sa.Column("ref_identity", sa.String(length=1024), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN edge_ref IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN assertion_ref IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_ri_derivations_single_parent",
        ),
        sa.CheckConstraint(
            "ref_kind IN ('observation', 'node', 'edge', 'assertion')",
            name="ck_ri_derivations_ref_kind",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "edge_ref"],
            ["ri_edges.snapshot_id", "ri_edges.id"],
            name="fk_ri_derivations_edge",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "assertion_ref"],
            ["ri_assertions.snapshot_id", "ri_assertions.id"],
            name="fk_ri_derivations_assertion",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ri_derivations_snapshot_id", "ri_derivations", ["snapshot_id"])
    for parent in ("edge", "assertion"):
        op.create_index(
            f"uq_ri_derivations_{parent}_fact",
            "ri_derivations",
            ["snapshot_id", f"{parent}_ref", "ref_kind", "ref_identity"],
            unique=True,
            sqlite_where=sa.text(f"{parent}_ref IS NOT NULL"),
            postgresql_where=sa.text(f"{parent}_ref IS NOT NULL"),
        )

    op.create_table(
        "ri_diagnostics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=48),
            sa.ForeignKey("ri_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("span_start_line", sa.Integer(), nullable=True),
        sa.Column("span_end_line", sa.Integer(), nullable=True),
        sa.Column("producer", sa.String(length=160), nullable=False),
        sa.Column("subject_key", sa.String(length=1024), nullable=True),
        sa.Column("object_key", sa.String(length=1024), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "severity IN ('fatal', 'error', 'warning', 'info')",
            name="ck_ri_diagnostics_severity",
        ),
        sa.CheckConstraint(
            "(span_start_line IS NULL AND span_end_line IS NULL) OR "
            "(span_start_line >= 1 AND span_end_line >= span_start_line)",
            name="ck_ri_diagnostics_span",
        ),
        sa.CheckConstraint("path IS NULL OR path NOT LIKE '/%'", name="ck_ri_diagnostics_relative_path"),
    )
    op.create_index("ix_ri_diagnostics_snapshot_id", "ri_diagnostics", ["snapshot_id"])


def upgrade() -> None:
    _add_repository_revision_columns()
    _backfill_repository_revisions()
    _create_snapshot_tables()


def downgrade() -> None:
    # Snapshot rows are intentionally discarded. Repository data that predates
    # this migration, including repo_metadata['commitSha'], is untouched.
    for table in (
        "ri_diagnostics",
        "ri_derivations",
        "ri_evidence",
        "ri_observations",
        "ri_assertions",
        "ri_edges",
        "ri_nodes",
        "ri_snapshots",
    ):
        op.drop_table(table)

    with op.batch_alter_table("repositories") as batch:
        batch.drop_index("ix_repositories_revision_value")
        batch.drop_constraint("ck_repositories_git_revision", type_="check")
        batch.drop_constraint("ck_repositories_upload_revision", type_="check")
        batch.drop_constraint("ck_repositories_revision_complete", type_="check")
        batch.drop_constraint("ck_repositories_revision_kind", type_="check")
        batch.drop_constraint("uq_repositories_id_revision", type_="unique")
        batch.drop_column("revision_ref")
        batch.drop_column("revision_value")
        batch.drop_column("revision_kind")
