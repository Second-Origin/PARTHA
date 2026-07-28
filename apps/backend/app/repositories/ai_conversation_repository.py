"""Owner- and repository-scoped persistence for AI Workspace conversation turns.

Every read and write here is scoped to both ``owner_id`` and ``repository_id``,
mirroring ``RepositoryRepository``'s owner-scoped accessors: a thread survives
navigation but a caller can never read or extend another owner's conversation.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai_conversation import AiConversationMessageRecord
from app.schemas.ai import AiCitation, AiMessage

# (role, content, citations, created_at) — one turn awaiting a sequence number.
AiConversationTurn = tuple[str, str, list[dict] | None, datetime]

# Bound the retries for sequence collisions. Concurrent allocations are rare in
# practice (one user, one thread), so a small cap is plenty and prevents an
# infinite loop if something else is wrong.
_MAX_SEQUENCE_RETRIES = 5


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
                role=turn.role,  # type: ignore[arg-type]
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

        The ``(owner_id, repository_id, sequence)`` uniqueness constraint is
        the concurrency guard: if two requests allocate the same next sequence
        simultaneously, one of them hits IntegrityError. We retry the whole
        allocation a bounded number of times so the collision resolves instead
        of silently interleaving pairs or 500-ing.
        """

        last_error: Exception | None = None
        for _ in range(_MAX_SEQUENCE_RETRIES):
            try:
                self._append_turns_once(repository_id, owner_id, turns)
                return
            except IntegrityError as exc:
                last_error = exc
                self.db.rollback()
        assert last_error is not None
        raise last_error

    def _append_turns_once(self, repository_id: str, owner_id: str, turns: list[AiConversationTurn]) -> None:
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
