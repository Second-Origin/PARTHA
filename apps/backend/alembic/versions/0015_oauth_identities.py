"""add oauth_identities, oauth_flow_states, oauth_pending_links

Revision ID: 0015_oauth_identities
Revises: 0014_lineage_constraints
Create Date: 2026-08-29

Issue #288: Google and GitHub sign-in, built with credentials deferred (no
real OAuth application is registered yet -- see the issue comment for what
still needs the owner before this can go live). Three new tables, no
changes to any existing one:

- ``oauth_identities``: durable, one row per linked (provider, PARTHA user)
  pair. A given external identity can only ever belong to one PARTHA
  account (unique on provider+subject); a user can link at most one
  identity per provider (unique on provider+user). Cascades on user
  deletion.
- ``oauth_flow_states``: one row per in-flight authorization request
  (CSRF state, PKCE verifier, OIDC nonce). Single-use and short-lived --
  the service deletes each row the moment its callback is consumed.
- ``oauth_pending_links``: one row per verified external identity whose
  email matched an existing account during a login attempt, awaiting the
  account owner's explicit password confirmation before the two identities
  are connected (never auto-linked by email match alone).
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_oauth_identities"
down_revision = "0014_lineage_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_oauth_identities_user_id_users"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_oauth_identities_provider_subject"),
        sa.UniqueConstraint("provider", "user_id", name="uq_oauth_identities_provider_user"),
    )
    op.create_index("ix_oauth_identities_user_id", "oauth_identities", ["user_id"])

    op.create_table(
        "oauth_flow_states",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=True),
        sa.Column("nonce", sa.String(length=64), nullable=True),
        sa.Column("intent", sa.String(length=16), nullable=False),
        sa.Column(
            "link_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_oauth_flow_states_link_user_id_users"),
            nullable=True,
        ),
        sa.Column("frontend_redirect_base", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("intent IN ('login', 'link')", name="ck_oauth_flow_states_intent"),
    )
    op.create_index("ix_oauth_flow_states_state_hash", "oauth_flow_states", ["state_hash"], unique=True)

    op.create_table(
        "oauth_pending_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oauth_pending_links")
    op.drop_index("ix_oauth_flow_states_state_hash", table_name="oauth_flow_states")
    op.drop_table("oauth_flow_states")
    op.drop_index("ix_oauth_identities_user_id", table_name="oauth_identities")
    op.drop_table("oauth_identities")
