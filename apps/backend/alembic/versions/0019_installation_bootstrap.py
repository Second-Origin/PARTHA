"""Persist the installation bootstrap claim independently of users.

Revision ID: 0019_installation_bootstrap
Revises: 0018_conversation_msg_indexes
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_installation_bootstrap"
down_revision = "0018_conversation_msg_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("installation_bootstrap", sa.Column("id", sa.String(32), primary_key=True))
    connection = op.get_bind()
    # Prior accounts, used approvals, and account deletion audits all establish
    # that setup has happened, even when no real account survives today.
    claimed = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM users WHERE id != :seed) "
            "OR EXISTS (SELECT 1 FROM approved_emails WHERE used_at IS NOT NULL) "
            "OR EXISTS (SELECT 1 FROM account_deletion_audits)"
        ),
        {"seed": "00000000-0000-0000-0000-000000000000"},
    ).scalar()
    if claimed:
        connection.execute(sa.text("INSERT INTO installation_bootstrap (id) VALUES ('installation')"))


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM installation_bootstrap")).scalar():
        raise RuntimeError(
            "Cannot remove a claimed installation bootstrap; restore a pre-upgrade backup to downgrade safely."
        )
    op.drop_table("installation_bootstrap")
