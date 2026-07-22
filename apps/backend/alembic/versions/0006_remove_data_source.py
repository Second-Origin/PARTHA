"""remove the meaningless repository data-source field

Revision ID: 0006_remove_data_source
Revises: 0006_analysis_jobs
Create Date: 2026-07-22

``repositories.source`` already records the actual repository provenance
(``upload`` or ``github``). The separate ``data_source`` column only ever held
the hardcoded value ``real`` and could not represent a meaningful state.
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_remove_data_source"
down_revision = "0006_analysis_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repositories") as batch:
        batch.drop_column("data_source")


def downgrade() -> None:
    with op.batch_alter_table("repositories") as batch:
        batch.add_column(sa.Column("data_source", sa.String(length=32), nullable=False, server_default="real"))
