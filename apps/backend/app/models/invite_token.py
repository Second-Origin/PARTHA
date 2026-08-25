from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InviteToken(Base):
    """One issued invite code (#341). Only the sha256 of the raw code is
    stored, the same construction as RefreshToken.token_hash -- a database
    read alone must never hand out a working invite.

    Redemption is single-use: ``redeemed_at`` is set exactly once, by the
    registration that consumes it, and a code with ``redeemed_at`` already
    set is rejected. ``redeemed_by_user_id`` is nullable and ``SET NULL`` on
    the user's deletion so a redeemed invite row outlives the account it
    created, the same audit-survives-deletion pattern as
    ``account_deletion_audits``.
    """

    __tablename__ = "invite_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Free-form operator note (e.g. which waitlist entry this was issued
    # for) -- never displayed to the registrant, purely for the owner's own
    # bookkeeping when issuing codes by hand.
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
