"""add invite_tokens for invite-gated registration

Revision ID: 0011_invite_tokens
Revises: 0010_account_deletion
Create Date: 2026-08-23

Issue #341: registration requires a single-use invite code issued by the
owner, rather than being open to anyone who reaches /register. Only the
sha256 hash of the raw code is stored (same construction as
refresh_tokens.token_hash) -- a database read alone must never hand out a
working invite.
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_invite_tokens"
down_revision = "0010_account_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "redeemed_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_invite_tokens_redeemed_by_user_id_users"),
            nullable=True,
        ),
    )
    op.create_index("ix_invite_tokens_code_hash", "invite_tokens", ["code_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invite_tokens_code_hash", table_name="invite_tokens")
    op.drop_table("invite_tokens")
