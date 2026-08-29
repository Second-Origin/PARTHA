"""add approved_emails, seed the product owner's address

Revision ID: 0016_approved_emails
Revises: 0015_oauth_identities
Create Date: 2026-08-29

Issue #374: replaces single-use invite codes (#341) with an admin-managed
approved-email allowlist as the registration gate. `invite_tokens` is left
in place as a historical audit record -- nothing drops it -- but nothing in
the live registration path consults it after this migration; only
``approved_emails`` does.

Seeds exactly one row: the product owner's own address, so this migration
can never lock him out of the very system it's gating. No other real
account email could be identified anywhere in this codebase to also seed --
the only pre-existing seed user (``users.id ==
'00000000-0000-0000-0000-000000000000'``) is an explicit non-login system
placeholder (``password_hash`` is null, and both the password-login and
OAuth-login paths already refuse to authenticate it), not a real owner
account, so it is deliberately not approved here.
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0016_approved_emails"
down_revision = "0015_oauth_identities"
branch_labels = None
depends_on = None

# Kept in one place so upgrade() and downgrade() can never disagree on which
# row this migration is responsible for.
_SEEDED_EMAIL = "parthrohit60@gmail.com"

approved_emails = sa.table(
    "approved_emails",
    sa.column("id", sa.String),
    sa.column("email", sa.String),
    sa.column("note", sa.String),
    sa.column("added_by", sa.String),
    sa.column("created_at", sa.DateTime),
)


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

    op.bulk_insert(
        approved_emails,
        [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "email": _SEEDED_EMAIL,
                "note": "Pre-approved: product owner, seeded by migration 0016 so this change can never lock him out.",
                "added_by": "migration:0016_approved_emails",
                "created_at": datetime.now(UTC),
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_approved_emails_email", table_name="approved_emails")
    op.drop_table("approved_emails")
