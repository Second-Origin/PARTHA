"""add durable analysis_jobs table for job state management

Revision ID: 0006_analysis_jobs
Revises: 0005_revision_snapshots
Create Date: 2026-07-21

This migration adds the analysis_jobs table to track durable job state across
worker claims and retries. The table uses a partial unique index to prevent
duplicate submissions (at most one queued/running job per identity), while
allowing history accumulation for completed/failed/cancelled jobs.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_analysis_jobs"
down_revision = "0005_revision_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("revision_kind", sa.String(length=16), nullable=False),
        sa.Column("revision_value", sa.String(length=80), nullable=False),
        sa.Column("config_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_id", sa.String(length=48), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_analysis_jobs_status",
        ),
        sa.CheckConstraint("revision_kind IN ('git','upload')", name="ck_analysis_jobs_revision_kind"),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_analysis_jobs_progress_range"),
        sa.CheckConstraint("attempt >= 0", name="ck_analysis_jobs_attempt_nonneg"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_analysis_jobs_max_attempts_positive"),
        sa.ForeignKeyConstraint(
            ["repository_id", "revision_kind", "revision_value"],
            ["repositories.id", "repositories.revision_kind", "repositories.revision_value"],
            name="fk_analysis_jobs_repository_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_analysis_jobs_owner", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["ri_snapshots.snapshot_id"], name="fk_analysis_jobs_snapshot", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_analysis_jobs_repository_id", "analysis_jobs", ["repository_id"])
    op.create_index("ix_analysis_jobs_owner_id", "analysis_jobs", ["owner_id"])
    op.create_index("ix_analysis_jobs_status_lease", "analysis_jobs", ["status", "lease_expires_at"])
    op.create_index(
        "uq_analysis_jobs_active_identity",
        "analysis_jobs",
        ["repository_id", "revision_value", "config_hash"],
        unique=True,
        sqlite_where=sa.text("status IN ('queued','running')"),
        postgresql_where=sa.text("status IN ('queued','running')"),
    )


def downgrade() -> None:
    op.drop_table("analysis_jobs")
