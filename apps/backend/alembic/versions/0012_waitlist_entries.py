"""add waitlist_entries for the public landing-page waitlist

Revision ID: 0012_waitlist_entries
Revises: 0011_invite_tokens
Create Date: 2026-08-23

Issue #334: the public landing page collects email/name signups for the
owner to review and invite manually, rather than open self-serve
registration. Deliberately not an account or an invite -- just a queue.
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_waitlist_entries"
down_revision = "0011_invite_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_waitlist_entries_email", "waitlist_entries", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_waitlist_entries_email", table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
