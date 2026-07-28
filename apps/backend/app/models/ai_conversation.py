from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiConversationMessageRecord(Base):
    """One persisted turn of an AI Workspace conversation.

    Every row is scoped to both ``owner_id`` and ``repository_id``: the AI
    Workspace keeps one ordered thread per repository per owner so history
    survives navigation away and back, and a cross-owner read resolves to the
    same 404 as a missing repository (see ``AiConversationRepository``).
    ``sequence`` orders turns within a thread explicitly rather than relying
    on timestamp precision, since the user and assistant turns of one query
    are written back to back in the same commit.
    """

    __tablename__ = "ai_conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
