"""enforce conversation FK cascade and sequence uniqueness

Revision ID: 0010_ai_conversation_cascade_and_sequence_unique
Revises: 0009_ai_conversation_messages
Create Date: 2026-07-28

The conversation table shipped in 0009 without a cascade on the
``repository_id`` foreign key and without a uniqueness guard on the
``(owner_id, repository_id, sequence)`` tuple. This migration hardens both:

* Deleting a repository must remove its conversation turns (ON DELETE
  CASCADE) instead of raising a foreign-key violation.
* Simultaneous sequence allocations must collide at the database rather than
  silently interleave user/assistant pairs, so a unique constraint is added.

SQLite creates the 0009 FK without an explicit name, so it cannot be dropped
by name. Dropping and re-adding the ``repository_id`` column (batch mode
preserves row data during the table rebuild) lets us install a named, cascading
foreign key portably across SQLite and PostgreSQL.
"""

from sqlalchemy import Column, ForeignKey, String

from alembic import op

revision = "0010_ai_conversation_cascade_and_sequence_unique"
down_revision = "0009_ai_conversation_messages"
branch_labels = None
depends_on = None

_FK_NAME = "fk_ai_conversation_messages_repository_id"
_UQ_NAME = "uq_ai_conversation_owner_repo_sequence"


def upgrade() -> None:
    with op.batch_alter_table("ai_conversation_messages") as batch_op:
        batch_op.drop_column("repository_id")
        batch_op.add_column(Column("repository_id", String(36), nullable=False))
        batch_op.create_foreign_key(
            _FK_NAME,
            "repositories",
            ["repository_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            _UQ_NAME,
            ["owner_id", "repository_id", "sequence"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_conversation_messages") as batch_op:
        batch_op.drop_constraint(_UQ_NAME, type_="unique")
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        batch_op.drop_column("repository_id")
        batch_op.add_column(Column("repository_id", String(36), nullable=False))
        batch_op.create_foreign_key(
            _FK_NAME,
            "repositories",
            ["repository_id"],
            ["id"],
        )
