"""add users table and repository owner

Revision ID: 0002_add_users_and_repository_owner
Revises: 0001_initial
Create Date: 2026-07-11
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = "0002_add_users_and_repository_owner"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

# Kept in sync with app.models.user.SEED_USER_ID / SEED_USER_EMAIL. Existing
# repositories predate authentication, so they are backfilled to this owner.
SEED_USER_ID = "00000000-0000-0000-0000-000000000000"
SEED_USER_EMAIL = "system@partha.local"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    now = datetime.now(UTC)
    users_table = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        users_table,
        [{"id": SEED_USER_ID, "email": SEED_USER_EMAIL, "is_active": True, "created_at": now, "updated_at": now}],
    )

    # Add owner_id with a server_default so existing rows backfill to the seed
    # user, then drop the default in a second step so new rows must set it
    # explicitly (the service always does). Split across two batch blocks because
    # SQLite recreates the table per block and the default must exist while the
    # data copy runs.
    with op.batch_alter_table("repositories") as batch:
        batch.add_column(
            sa.Column("owner_id", sa.String(length=36), nullable=False, server_default=SEED_USER_ID)
        )
        batch.create_index("ix_repositories_owner_id", ["owner_id"], unique=False)
        batch.create_foreign_key("fk_repositories_owner_id_users", "users", ["owner_id"], ["id"])

    with op.batch_alter_table("repositories") as batch:
        batch.alter_column("owner_id", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("repositories") as batch:
        batch.drop_constraint("fk_repositories_owner_id_users", type_="foreignkey")
        batch.drop_index("ix_repositories_owner_id")
        batch.drop_column("owner_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
