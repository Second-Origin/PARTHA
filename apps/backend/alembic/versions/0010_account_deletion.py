"""add account-deletion cascades and audit trail

Revision ID: 0010_account_deletion
Revises: 0009_ai_conversation_messages
Create Date: 2026-08-13

Issue #290: verified account deletion. Several owner foreign keys did not
declare database-level cascade deletion, so deleting a ``users`` row would
raise a foreign-key violation unless every owned row was deleted in exactly
the right order first. This adds ``ON DELETE CASCADE`` as a second line of
defense behind the application-level deletion in ``AccountDeletionService``,
and adds a minimal, non-PII audit trail that survives the user row itself
being deleted.

``refresh_tokens.user_id``, ``ai_provider_configs.owner_id``, and
``ai_conversation_messages.owner_id`` were all created inline
(``sa.ForeignKey("users.id")``) with no explicit constraint name, so
PostgreSQL and SQLite ended up with different anonymous identities for the
"same" constraint:

- PostgreSQL auto-names an unnamed single-column foreign key
  ``<table>_<column>_fkey`` (verified against a live instance --
  ``refresh_tokens_user_id_fkey`` etc -- this is Postgres's own naming, not
  SQLAlchemy's, so it is stable to rely on here).
- SQLite does not name inline ``REFERENCES`` constraints at all; reflection
  reports ``name=None``, and batch mode can only drop a *named* constraint.
  The SQLite branch below supplies its own ``naming_convention`` so batch
  mode can synthesize a deterministic name for the anonymous constraint
  before dropping it. Verified end-to-end against a live SQLite file with
  ``PRAGMA foreign_keys=ON``: the resulting constraint reports
  ``ON DELETE CASCADE`` in ``PRAGMA foreign_key_list`` and a parent-row
  delete actually removes the child row.

``repositories.owner_id`` already has an explicit name from migration 0002
(``fk_repositories_owner_id_users``) on both dialects, but SQLite still needs
the same anonymous-constraint workaround as the other three: SQLite never
persists a foreign key's constraint name (``PRAGMA foreign_key_list`` has no
name column), so reflection reports ``name=None`` regardless of how the
constraint was originally created, and batch mode can only drop a *named*
constraint. It is folded into ``_OWNER_FKS`` below rather than handled as a
one-off so both dialects go through the same branch.
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_account_deletion"
down_revision = "0009_ai_conversation_messages"
branch_labels = None
depends_on = None

_SQLITE_ANON_FK_NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}

# (table, column, new constraint name, existing Postgres auto-generated name)
_OWNER_FKS = [
    (
        "refresh_tokens",
        "user_id",
        "fk_refresh_tokens_user_id_users",
        "refresh_tokens_user_id_fkey",
    ),
    (
        "ai_provider_configs",
        "owner_id",
        "fk_ai_provider_configs_owner_id_users",
        "ai_provider_configs_owner_id_fkey",
    ),
    (
        "ai_conversation_messages",
        "owner_id",
        "fk_ai_conversation_messages_owner_id_users",
        "ai_conversation_messages_owner_id_fkey",
    ),
    (
        "repositories",
        "owner_id",
        "fk_repositories_owner_id_users",
        "fk_repositories_owner_id_users",
    ),
]


def upgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    for table, column, new_name, pg_existing_name in _OWNER_FKS:
        if is_sqlite:
            with op.batch_alter_table(table, naming_convention=_SQLITE_ANON_FK_NAMING_CONVENTION) as batch_op:
                batch_op.drop_constraint(new_name, type_="foreignkey")
                batch_op.create_foreign_key(new_name, "users", [column], ["id"], ondelete="CASCADE")
        else:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_constraint(pg_existing_name, type_="foreignkey")
                batch_op.create_foreign_key(new_name, "users", [column], ["id"], ondelete="CASCADE")

    op.create_table(
        "account_deletion_audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        # Deliberately not a foreign key: the referenced user row is gone by
        # the time a row here reaches "completed", and the point of an audit
        # trail is that it outlives the thing it records. No email or other
        # personal data is stored -- only the id that was deleted.
        sa.Column("deleted_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress','completed','failed')",
            name="ck_account_deletion_audits_status",
        ),
    )
    op.create_index("ix_account_deletion_audits_deleted_user_id", "account_deletion_audits", ["deleted_user_id"])


def downgrade() -> None:
    op.drop_index("ix_account_deletion_audits_deleted_user_id", table_name="account_deletion_audits")
    op.drop_table("account_deletion_audits")

    is_sqlite = op.get_bind().dialect.name == "sqlite"

    for table, column, new_name, _pg_existing_name in reversed(_OWNER_FKS):
        if is_sqlite:
            with op.batch_alter_table(table, naming_convention=_SQLITE_ANON_FK_NAMING_CONVENTION) as batch_op:
                batch_op.drop_constraint(new_name, type_="foreignkey")
                batch_op.create_foreign_key(new_name, "users", [column], ["id"])
        else:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_constraint(new_name, type_="foreignkey")
                batch_op.create_foreign_key(new_name, "users", [column], ["id"])
