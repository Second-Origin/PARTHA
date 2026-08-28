from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_CANONICAL_PARTIAL_WHERE = text("canonical_source_key IS NOT NULL AND canonical_branch IS NOT NULL")


class RepositoryLineage(Base):
    """Durable, owner-scoped logical grouping above repository revisions (#299, RFC-0002).

    A row here groups repeated imports of the same GitHub repository/branch
    into one ordered history. Uploads and unresolved-ref GitHub rows never get
    a row here -- they stay unlineaged standalone imports (RFC §4.3/§6) -- so
    ``canonical_source_key``/``canonical_branch`` and every ``repositories``
    attachment are permanently optional, not a transitional NULL.
    """

    __tablename__ = "repository_lineages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    canonical_source_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text)
    # The current highest surviving sequence in this lineage, or null for an
    # empty lineage. This FK is deferrable/initially-deferred and cyclic with
    # `repositories`: a lineage must exist (with a null pointer) before its
    # first repository can be inserted, and the pointer is only set afterward,
    # in the same transaction (RFC §5.1/§5.2).
    latest_repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Durable, never-reused, transactionally-allocated next ordinal. Starts at
    # 1; deleting a repository never decrements it (RFC §4.3).
    next_sequence: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        # Composite ownership FK target for `repositories.lineage_id`.
        UniqueConstraint("id", "owner_id", name="uq_repository_lineages_id_owner"),
        CheckConstraint(
            "(canonical_source_key IS NULL AND canonical_branch IS NULL) OR "
            "(canonical_source_key IS NOT NULL AND canonical_branch IS NOT NULL)",
            name="ck_repository_lineages_canonical_pair",
        ),
        CheckConstraint("next_sequence >= 1", name="ck_repository_lineages_next_sequence_positive"),
        ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_repository_lineages_owner_id_users",
            ondelete="CASCADE",
        ),
        # The owner-scoped canonical lookup index, and the sole source of
        # "does this lineage already exist" truth if two imports race to
        # create the first one (RFC §5.2).
        Index(
            "uq_repository_lineages_owner_source_branch",
            "owner_id",
            "canonical_source_key",
            "canonical_branch",
            unique=True,
            postgresql_where=_CANONICAL_PARTIAL_WHERE,
            sqlite_where=_CANONICAL_PARTIAL_WHERE,
        ),
        # The cyclic half of the lineage/repository integrity boundary (RFC
        # §4.2): a latest-pointer can never name a repository outside this
        # exact lineage, even if service code is wrong. Declared here (rather
        # than only in the migration) so `create_all()` in development/test
        # produces the identical final shape a migrated database reaches.
        ForeignKeyConstraint(
            ["latest_repository_id", "id"],
            ["repositories.id", "repositories.lineage_id"],
            name="fk_repository_lineages_latest_member",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
