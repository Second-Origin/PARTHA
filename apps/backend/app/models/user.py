from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# The system/seed user that owns repositories created before authentication
# existed. The 0002 migration backfills those rows to this owner. It has no
# credential and cannot log in, and since E1.3 removed the pre-auth fallback no
# live request is ever attributed to it — it exists only so historical data has
# a valid owner. The id is fixed so the migration backfill agrees with it.
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
