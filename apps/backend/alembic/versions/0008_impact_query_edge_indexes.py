"""add directional snapshot-edge indexes for impact traversal

Revision ID: 0008_impact_query_edge_indexes
Revises: 0007_remove_data_source
Create Date: 2026-07-28

The sealed-snapshot impact query filters resolved edges by snapshot, one
endpoint direction, and predicate. These complementary composite indexes keep
both outgoing dependency and incoming dependent lookups bounded as snapshots
grow.
"""

from __future__ import annotations

from alembic import op

revision = "0008_impact_query_edge_indexes"
down_revision = "0007_remove_data_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ri_edges_snapshot_subject_predicate",
        "ri_edges",
        ["snapshot_id", "subject_key", "predicate"],
    )
    op.create_index(
        "ix_ri_edges_snapshot_object_predicate",
        "ri_edges",
        ["snapshot_id", "object_key", "predicate"],
    )


def downgrade() -> None:
    op.drop_index("ix_ri_edges_snapshot_object_predicate", table_name="ri_edges")
    op.drop_index("ix_ri_edges_snapshot_subject_predicate", table_name="ri_edges")
