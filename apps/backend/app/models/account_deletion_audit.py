from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AccountDeletionAuditRecord(Base):
    """A minimal, non-PII record that an account deletion happened.

    Deliberately holds no foreign key to ``users``: the whole point of an
    audit trail is that it survives the row it describes, and by the time a
    row here reaches ``completed`` the referenced user no longer exists.
    Nothing beyond the id that was deleted is retained -- no email, no
    repository data, no credentials (#290).
    """

    __tablename__ = "account_deletion_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    deleted_user_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(16))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress','completed','failed')",
            name="ck_account_deletion_audits_status",
        ),
    )
