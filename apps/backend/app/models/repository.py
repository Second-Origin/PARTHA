from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base


def _hex_only_sql(expression: str) -> str:
    """Portable SQLite/PostgreSQL check that ``expression`` is lowercase hex."""

    for character in "0123456789abcdef":
        expression = f"replace({expression}, '{character}', '')"
    return f"{expression} = ''"


class RepositoryRecord(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # First-class revision identity (#87, RFC §3). ``revision_value`` is the
    # immutable, indexed identity: the 40-char lowercase git commit SHA for
    # GitHub imports, or the ``sha256:<hex>`` archive content hash for uploads.
    # ``revision_ref`` is the resolved-but-moving ref (e.g. ``refs/heads/main``)
    # and is descriptive metadata only — never identity. A moving branch name is
    # never a substitute for the revision value.
    revision_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    revision_value: Mapped[str | None] = mapped_column(String(80), nullable=True)
    revision_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_path: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True)
    data_source: Mapped[str] = mapped_column(String(32), default="real")
    analysis_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_progress: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    analysed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_tree: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        # Composite target for snapshot revision ownership. ``id`` is already
        # unique, but including the revision columns lets the snapshot FK prove
        # that a snapshot cannot be attached to a different repository revision.
        UniqueConstraint(
            "id",
            "revision_kind",
            "revision_value",
            name="uq_repositories_id_revision",
        ),
        CheckConstraint(
            "revision_kind IS NULL OR revision_kind IN ('git', 'upload')",
            name="ck_repositories_revision_kind",
        ),
        CheckConstraint(
            "(revision_kind IS NULL AND revision_value IS NULL AND revision_ref IS NULL) OR "
            "(revision_kind IS NOT NULL AND revision_value IS NOT NULL)",
            name="ck_repositories_revision_complete",
        ),
        CheckConstraint(
            "revision_kind <> 'upload' OR "
            f"(revision_ref IS NULL AND length(revision_value) = 71 AND "
            f"substr(revision_value, 1, 7) = 'sha256:' AND {_hex_only_sql('substr(revision_value, 8)')})",
            name="ck_repositories_upload_revision",
        ),
        CheckConstraint(
            "revision_kind <> 'git' OR "
            f"(length(revision_value) = 40 AND {_hex_only_sql('revision_value')} AND "
            "(revision_ref IS NULL OR revision_ref LIKE 'refs/%'))",
            name="ck_repositories_git_revision",
        ),
        Index("ix_repositories_revision_value", "revision_value"),
    )

    @validates("revision_kind", "revision_value")
    def _enforce_immutable_revision_identity(self, key: str, value: str | None) -> str | None:
        """Revision identity is immutable once written (#87, RFC §3.2).

        A new commit or upload content hash produces a *new* repository record
        rather than mutating an existing identity, so any attempt to change an
        already-written ``revision_value`` is rejected. Setting it for the first
        time (``None`` -> value) and idempotent re-writes are allowed; loads from
        the database do not pass through this validator.
        """

        current = getattr(self, key, None)
        if current is not None and value != current:
            raise ValueError("Repository revision identity is immutable once written.")
        return value
