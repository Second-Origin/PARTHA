"""Owner- and repository-scoped persistence for AI Workspace conversation turns.

Every read and write here is scoped to both ``owner_id`` and ``repository_id``,
mirroring ``RepositoryRepository``'s owner-scoped accessors: a thread survives
navigation but a caller can never read or extend another owner's conversation.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_conversation import AiConversationMessageRecord
from app.schemas.ai import AiCitation, AiMessage

# (role, content, citations, created_at) — one turn awaiting a sequence number.
AiConversationTurn = tuple[str, str, list[dict] | None, datetime]


class AiConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_conversation(self, repository_id: str, owner_id: str) -> list[AiMessage]:
        statement = (
            select(AiConversationMessageRecord)
            .where(
                AiConversationMessageRecord.repository_id == repository_id,
                AiConversationMessageRecord.owner_id == owner_id,
            )
            .order_by(AiConversationMessageRecord.sequence)
        )
        turns = self.db.scalars(statement).all()
        return [
            AiMessage(
                role=turn.role,
                content=turn.content,
                timestamp=turn.created_at,
                citations=[AiCitation(**citation) for citation in turn.citations] if turn.citations else None,
            )
            for turn in turns
        ]

    def append_turns(self, repository_id: str, owner_id: str, turns: list[AiConversationTurn]) -> None:
        """Persist ordered turns in one commit.

        Called with both the user turn and its assistant reply together, so a
        query can never leave a user turn stored without its answer, or
        vice versa.
        """

        next_sequence = self._next_sequence(repository_id, owner_id)
        for offset, (role, content, citations, created_at) in enumerate(turns):
            self.db.add(
                AiConversationMessageRecord(
                    id=str(uuid4()),
                    owner_id=owner_id,
                    repository_id=repository_id,
                    sequence=next_sequence + offset,
                    role=role,
                    content=content,
                    citations=citations,
                    created_at=created_at,
                )
            )
        self.db.commit()

    def _next_sequence(self, repository_id: str, owner_id: str) -> int:
        statement = select(func.max(AiConversationMessageRecord.sequence)).where(
            AiConversationMessageRecord.repository_id == repository_id,
            AiConversationMessageRecord.owner_id == owner_id,
        )
        current_max = self.db.scalar(statement)
        return 0 if current_max is None else current_max + 1
