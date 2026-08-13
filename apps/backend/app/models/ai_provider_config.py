from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiProviderConfigRecord(Base):
    """A single user's active AI provider configuration.

    One row per owner (``owner_id`` is unique): saving a new configuration
    replaces the previous one, mirroring the single-active-provider model the
    UI presents. The API key is stored only as Fernet ciphertext in
    ``encrypted_api_key`` — never in plaintext — and ``api_key_last4`` holds the
    last four characters so the UI can confirm which key is saved without the
    key ever being decrypted for display.
    """

    __tablename__ = "ai_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32))
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
