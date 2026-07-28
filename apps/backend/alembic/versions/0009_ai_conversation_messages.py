"""add ai conversation message persistence

Revision ID: 0009_ai_conversation_messages
Revises: 0008_impact_query_edge_indexes
Create Date: 2026-07-28

The AI Workspace previously lost its conversation thread on every navigation
away from the page because nothing was ever persisted server-side (#231).
This adds one row per turn (user or assistant), scoped by owner and
repository, ordered within a thread by ``sequence`` rather than timestamp
precision.
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_ai_conversation_messages"
down_revision = "0008_impact_query_edge_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversation_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("repository_id", sa.String(length=36), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Serves both the owner+repository scoping check on every read and the
    # in-thread ordering, in one composite index.
    op.create_index(
        "ix_ai_conversation_messages_owner_repository_sequence",
        "ai_conversation_messages",
        ["owner_id", "repository_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_conversation_messages_owner_repository_sequence", table_name="ai_conversation_messages")
    op.drop_table("ai_conversation_messages")
