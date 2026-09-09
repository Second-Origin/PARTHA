from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OAuthIdentity(Base):
    """One linked external sign-in identity for one PARTHA user (#288).

    A user may link at most one identity per provider (the unique
    constraint on ``(provider, user_id)``), and a given external identity
    may only ever be linked to one PARTHA account (the unique constraint on
    ``(provider, provider_subject)``) -- linking never silently merges two
    accounts. An email match alone is never sufficient to link; see
    ``OAuthPendingLink`` for the explicit-confirmation path that applies
    when a discovered identity's email belongs to an existing account.
    """

    __tablename__ = "oauth_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    # The provider's stable, verified subject identifier (Google: the OIDC
    # `sub` claim; GitHub: the numeric account id, as a string) -- never the
    # email, which can change at the provider and is not identity.
    provider_subject: Mapped[str] = mapped_column(String(255))
    # The verified email at link time, kept only for display in Settings'
    # linked-account list; never re-verified or kept in sync afterward.
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_oauth_identities_provider_subject"),
        UniqueConstraint("provider", "user_id", name="uq_oauth_identities_provider_user"),
    )
