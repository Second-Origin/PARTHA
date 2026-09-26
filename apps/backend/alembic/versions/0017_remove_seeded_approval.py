"""remove the seeded pre-approved address from databases that already ran 0016

Revision ID: 0017_remove_seeded_approval
Revises: 0016_approved_emails
Create Date: 2026-09-26

Issue #465: the original ``0016_approved_emails`` inserted one hardcoded
address into ``approved_emails``. Registration has no email verification,
so on any instance that already has users, anyone who knew that address
(it was public in source) could register it and get an account past the
allowlist the operator was relying on. ``0016`` no longer seeds it, so a
fresh database never has the row; this revision removes it from databases
that already ran the old ``0016``.

Only the untouched seed is removed -- the same fixed id, the same
``added_by`` marker, and ``used_at IS NULL``. A row that was already used to
register an account is left alone: that account exists, and a migration
can't tell its owner from anyone else. Approval is consulted only when an
account is created, never at login, so removing an unused row cannot lock
anyone out of an existing account.

The downgrade is deliberately a no-op: reverting this revision must not
re-open the hole by re-inserting the row.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_remove_seeded_approval"
down_revision = "0016_approved_emails"
branch_labels = None
depends_on = None

# Identify the seed by its id and marker, not its address, so this file
# doesn't have to repeat the address it exists to remove.
_SEED_ID = "00000000-0000-0000-0000-000000000001"
_SEED_ADDED_BY = "migration:0016_approved_emails"

approved_emails = sa.table(
    "approved_emails",
    sa.column("id", sa.String),
    sa.column("added_by", sa.String),
    sa.column("used_at", sa.DateTime),
)


def upgrade() -> None:
    op.execute(
        approved_emails.delete().where(
            approved_emails.c.id == _SEED_ID,
            approved_emails.c.added_by == _SEED_ADDED_BY,
            approved_emails.c.used_at.is_(None),
        )
    )


def downgrade() -> None:
    # Intentionally empty: see the module docstring.
    pass
