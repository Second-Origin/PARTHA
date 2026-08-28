from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OAuthPendingLink(Base):
    """A verified external identity discovered during sign-in whose email
    matches an existing PARTHA account that has not linked this provider
    yet (#288).

    Never auto-linked -- a matching email is not proof of ownership. The
    account owner must confirm with their password
    (``POST /auth/oauth/link/confirm``) before the two identities are
    connected. Single-use and short-lived: deleted once confirmed, expired,
    or superseded by a fresh attempt.
    """

    __tablename__ = "oauth_pending_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
