from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
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
    # Durable logical grouping above revisions (#299, RFC-0002). Both remain
    # permanently nullable: an upload or an unresolved-ref legacy GitHub row
    # is a standalone import with no lineage, by design (RFC §4.3/§6), not a
    # transitional state to be tightened later.
    lineage_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_path: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True)
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
        CheckConstraint(
            "(lineage_id IS NULL AND sequence IS NULL) OR "
            "(lineage_id IS NOT NULL AND sequence IS NOT NULL AND sequence >= 1)",
            name="ck_repositories_lineage_sequence_pair",
        ),
        # Standalone rows (both null) never collide under a unique constraint:
        # SQL uniqueness treats every NULL as distinct. Also serves ordered
        # lineage reads.
        UniqueConstraint("lineage_id", "sequence", name="uq_repositories_lineage_sequence"),
        # Composite target proving a lineage's latest-member pointer names a
        # repository that actually belongs to that exact lineage.
        UniqueConstraint("id", "lineage_id", name="uq_repositories_id_lineage"),
        # Cross-owner attachment is invalid at the database layer even if
        # service code is wrong (#299 §9). Deferred: a lineage and its first
        # repository are written in one transaction (RFC §5.2), so this must
        # not be checked until commit. No automatic delete action -- deletion
        # updates or clears the lineage's latest pointer explicitly first
        # (RFC §8.3), it is never left to a database cascade/set-null here.
        ForeignKeyConstraint(
            ["lineage_id", "owner_id"],
            ["repository_lineages.id", "repository_lineages.owner_id"],
            name="fk_repositories_lineage_owner",
            deferrable=True,
            initially="DEFERRED",
        ),
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
