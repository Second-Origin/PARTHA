"""add per-user encrypted ai provider configs

Revision ID: 0004_ai_provider_configs
Revises: 0003_auth_credentials
Create Date: 2026-07-15

Revision ids stay under 32 characters: alembic_version.version_num is
VARCHAR(32) and PostgreSQL enforces it.

Replaces the single global ``ai-provider.json`` file with a per-user table.
The API key is stored only as Fernet ciphertext (``encrypted_api_key``); the
plaintext key is never persisted. There is intentionally no data migration:
the old global file held one deployment-wide key with no owner, so it cannot be
attributed to a user and is dropped rather than silently re-homed onto someone.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_ai_provider_configs"
down_revision = "0003_auth_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("api_key_last4", sa.String(length=4), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Unique so each user has exactly one active provider configuration; the
    # index also serves the owner-scoped lookup on every AI request.
    op.create_index("ix_ai_provider_configs_owner_id", "ai_provider_configs", ["owner_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ai_provider_configs_owner_id", table_name="ai_provider_configs")
    op.drop_table("ai_provider_configs")
