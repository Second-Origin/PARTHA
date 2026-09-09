"""close the repository-lineage cyclic integrity boundary (2 of 2)

Revision ID: 0014_lineage_constraints
Revises: 0013_lineage_expand
Create Date: 2026-08-27

Issue #299 (RFC-0002), part 2 of 2. Adds the one constraint that genuinely
needs both sides of the lineage/repository relationship to already exist:
``repository_lineages.latest_repository_id`` (together with ``id``) must
name a row in ``repositories`` whose own ``lineage_id`` points back at this
exact lineage -- a latest pointer can never name a repository in a
different lineage, or a different owner's repository, even if application
code is wrong.

Split from Revision A specifically so a failure here leaves A's state
additive, backward-compatible, and inspectable/fixable before rerunning
this one (plan §7). The new application must not start unless Alembic is at
this revision or later -- do not start code that assumes the latest-member
invariant against a database still only at Revision A.
"""

from alembic import op

revision = "0014_lineage_constraints"
down_revision = "0013_lineage_expand"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repository_lineages") as batch:
        batch.create_foreign_key(
            "fk_repository_lineages_latest_member",
            "repositories",
            ["latest_repository_id", "id"],
            ["id", "lineage_id"],
            deferrable=True,
            initially="DEFERRED",
        )


def downgrade() -> None:
    with op.batch_alter_table("repository_lineages") as batch:
        batch.drop_constraint("fk_repository_lineages_latest_member", type_="foreignkey")
