"""add password hash and refresh tokens

Revision ID: 0003_auth_credentials
Revises: 0002_users_and_repo_owner
Create Date: 2026-07-11

Revision ids stay under 32 characters: alembic_version.version_num is
VARCHAR(32) and PostgreSQL enforces it.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_auth_credentials"
down_revision = "0002_users_and_repo_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable on purpose: pre-auth rows (including the seed user) have no
    # credential and must never become logins by accident.
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_hash")
