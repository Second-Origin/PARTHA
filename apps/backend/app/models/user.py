from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# The system/seed user that owns all data created before authentication existed.
# Requests without an authenticated identity fall back to this owner until E1.2
# introduces real sign-in. The id is fixed so the 0002 migration backfill and the
# current-user seam agree on it; keep both in sync with these constants.
SEED_USER_ID = "00000000-0000-0000-0000-000000000000"
SEED_USER_EMAIL = "system@partha.local"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 320 is the RFC 5321 maximum length for an email address.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Nullable: the seed user and rows created before authentication have no
    # credential and must never be able to log in (login rejects a null hash).
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
