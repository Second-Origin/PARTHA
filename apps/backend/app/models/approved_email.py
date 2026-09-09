from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApprovedEmail(Base):
    """One admin-approved email address, the registration gate for the
    invite-only beta (#374, superseding the single-use invite codes of
    #341).

    Unlike an invite code, an approved email is not a scarce secret and is
    not consumed by use: it stays approved indefinitely, and re-registering
    the same email a second time is already rejected by `User.email`'s own
    uniqueness constraint regardless of this table's state. `used_at`/
    `used_by_user_id` are purely informational -- mirroring the spirit of
    `InviteToken`'s audit trail (who/when) -- not a gate.
    """

    __tablename__ = "approved_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Free-form operator note (e.g. which waitlist entry this was approved
    # for) -- never displayed to the registrant.
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Free text, not a User FK: there is no admin-role concept in this app,
    # and whoever runs scripts/approve_email.py is not necessarily a PARTHA
    # account at all. Purely an operator-facing audit label.
    added_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
