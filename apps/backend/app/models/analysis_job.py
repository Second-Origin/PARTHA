from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    revision_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    revision_value: Mapped[str] = mapped_column(String(80), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_analysis_jobs_status",
        ),
        CheckConstraint("revision_kind IN ('git','upload')", name="ck_analysis_jobs_revision_kind"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_analysis_jobs_progress_range"),
        CheckConstraint("attempt >= 0", name="ck_analysis_jobs_attempt_nonneg"),
        CheckConstraint("max_attempts >= 1", name="ck_analysis_jobs_max_attempts_positive"),
        ForeignKeyConstraint(
            ["repository_id", "revision_kind", "revision_value"],
            ["repositories.id", "repositories.revision_kind", "repositories.revision_value"],
            name="fk_analysis_jobs_repository_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_analysis_jobs_owner", ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["snapshot_id"], ["ri_snapshots.snapshot_id"], name="fk_analysis_jobs_snapshot", ondelete="SET NULL"
        ),
        Index("ix_analysis_jobs_repository_id", "repository_id"),
        Index("ix_analysis_jobs_owner_id", "owner_id"),
        Index("ix_analysis_jobs_status_lease", "status", "lease_expires_at"),
        Index(
            "uq_analysis_jobs_active_identity",
            "repository_id",
            "revision_value",
            "config_hash",
            unique=True,
            sqlite_where=text("status IN ('queued','running')"),
            postgresql_where=text("status IN ('queued','running')"),
        ),
    )
