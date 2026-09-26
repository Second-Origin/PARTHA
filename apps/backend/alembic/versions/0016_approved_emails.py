"""add approved_emails

Revision ID: 0016_approved_emails
Revises: 0015_oauth_identities
Create Date: 2026-08-29

Issue #374: replaces single-use invite codes (#341) with an admin-managed
approved-email allowlist as the registration gate. `invite_tokens` is left
in place as a historical audit record -- nothing drops it -- but nothing in
the live registration path consults it after this migration; only
``approved_emails`` does.

This revision originally also seeded one hardcoded address as pre-approved.
That was removed (#465): registration has no email verification, so a
pre-approved address that is public in source is claimable by anyone on any
instance. Owners are established by the first-user bootstrap (#388), not by a
seed. Databases that already ran the old version of this revision have the
row removed by ``0017_remove_seeded_approval``.
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_approved_emails"
down_revision = "0015_oauth_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approved_emails",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("added_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "used_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_approved_emails_used_by_user_id_users"),
            nullable=True,
        ),
        sa.UniqueConstraint("email", name="uq_approved_emails_email"),
    )
    op.create_index("ix_approved_emails_email", "approved_emails", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_approved_emails_email", table_name="approved_emails")
    op.drop_table("approved_emails")
