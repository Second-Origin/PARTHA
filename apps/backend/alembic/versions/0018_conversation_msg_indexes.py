"""index ai_conversation_messages by owner and repository

Revision ID: 0018_conversation_msg_indexes
Revises: 0017_remove_seeded_approval
Create Date: 2026-09-26

Issue #483: the ORM declares ``index=True`` on ``owner_id`` and
``repository_id`` of ``ai_conversation_messages``, so a database built with
``create_all`` has both indexes, but ``0009_ai_conversation_messages`` never
created them -- a migrated database (the normal upgrade path) lacked them, and
the per-repository conversation lookups it serves ran unindexed.

``if_not_exists`` because a database created by ``create_all`` and then
stamped at head already has them.
"""

from alembic import op

revision = "0018_conversation_msg_indexes"
down_revision = "0017_remove_seeded_approval"
branch_labels = None
depends_on = None

_TABLE = "ai_conversation_messages"


def upgrade() -> None:
    op.create_index("ix_ai_conversation_messages_owner_id", _TABLE, ["owner_id"], if_not_exists=True)
    op.create_index("ix_ai_conversation_messages_repository_id", _TABLE, ["repository_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_ai_conversation_messages_repository_id", table_name=_TABLE, if_exists=True)
    op.drop_index("ix_ai_conversation_messages_owner_id", table_name=_TABLE, if_exists=True)
