"""remove the always-"real" data_source placeholder column

Revision ID: 0007_remove_data_source
Revises: 0006_analysis_jobs
Create Date: 2026-07-25

``data_source`` was written as the literal "real" on every repository, never
derived from any actual distinction (#96). Downgrade restores the column with
its original server default so existing rows remain valid if reversed.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_remove_data_source"
down_revision = "0006_analysis_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repositories") as batch:
        batch.drop_column("data_source")


def downgrade() -> None:
    with op.batch_alter_table("repositories") as batch:
        batch.add_column(
            sa.Column("data_source", sa.String(length=32), nullable=False, server_default="real")
        )
