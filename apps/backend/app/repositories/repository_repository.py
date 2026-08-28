from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.repository import RepositoryRecord
from app.models.repository_lineage import RepositoryLineage

# Bound retries for two distinct races (#299, RFC-0002 §5.2): two importers
# racing to create the *first* lineage for a canonical key (one loses the
# unique index and must reload/retry), and a lineage-scoped duplicate-commit
# rollback. Five matches AiConversationRepository's own sequence-collision cap.
_MAX_LINEAGE_RETRIES = 5


class LineageDuplicateRevision(Exception):
    """The transactional insert found this exact commit already in the lineage.

    Carries the existing record so the caller can build the same 409 detail
    (`repositoryId`, `name`) the pre-clone fast-path check already returns,
    without a second query.
    """

    def __init__(self, existing: RepositoryRecord) -> None:
        self.existing = existing
        super().__init__("Repository revision already exists in this lineage.")


class RepositoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # Owner-scoped access only. Every repository lookup a request can reach goes
    # through one of these so a caller can only ever see its own repositories,
    # and ownership can't be forgotten by a new service: the unscoped variants
    # were removed in E1.3 (#63) once analysis/ai/documentation/export were
    # threaded onto the current user. Add owner-scoped accessors here, not
    # unscoped ones.
    def list_for_owner(self, owner_id: str) -> list[RepositoryRecord]:
        statement = (
            select(RepositoryRecord)
            .where(RepositoryRecord.owner_id == owner_id)
            .order_by(RepositoryRecord.uploaded_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def get_for_owner(self, repository_id: str, owner_id: str) -> RepositoryRecord | None:
        record = self.db.get(RepositoryRecord, repository_id)
        if record is None or record.owner_id != owner_id:
            return None
        return record

    def find_by_revision_for_owner(self, revision_value: str, owner_id: str) -> RepositoryRecord | None:
        """Find an owner's upload already imported at this exact content hash."""
        statement = select(RepositoryRecord).where(
            RepositoryRecord.revision_value == revision_value,
            RepositoryRecord.owner_id == owner_id,
        )
        return self.db.scalars(statement).first()

    def add(self, record: RepositoryRecord) -> RepositoryRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def save(self, record: RepositoryRecord) -> RepositoryRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete(self, record: RepositoryRecord) -> None:
        self.db.delete(record)
        self.db.commit()

    def delete_with_lineage_update(self, record: RepositoryRecord) -> None:
        """Delete `record`, rolling its lineage's latest pointer back first if needed.

        A standalone record (``lineage_id is None``) deletes exactly as
        ``delete()`` does. A lineaged record's deletion and any resulting
        latest-pointer change happen in one transaction (#299 §8.3): the
        counter never decreases, and an empty lineage is kept (null latest,
        preserved ``next_sequence``) rather than removed.
        """
        if record.lineage_id is not None:
            lineage = self.db.execute(
                select(RepositoryLineage).where(RepositoryLineage.id == record.lineage_id).with_for_update()
            ).scalar_one()
            if lineage.latest_repository_id == record.id:
                next_latest = self.db.scalars(
                    select(RepositoryRecord.id)
                    .where(
                        RepositoryRecord.lineage_id == record.lineage_id,
                        RepositoryRecord.id != record.id,
                    )
                    .order_by(RepositoryRecord.sequence.desc())
                    .limit(1)
                ).first()
                lineage.latest_repository_id = next_latest
        self.db.delete(record)
        self.db.commit()

    def add_with_lineage(
        self,
        record: RepositoryRecord,
        *,
        owner_id: str,
        canonical_source_key: str | None,
        canonical_branch: str | None,
        display_name: str,
    ) -> RepositoryRecord:
        """Insert `record`, allocating it into an owner-scoped lineage keyed by
        the given canonical pair (#299, RFC-0002 §5.2). A null pair inserts a
        standalone import with no lineage, identical to plain ``add()`` --
        uploads and unresolved-ref imports always take this branch.

        Lineage find-or-create, sequence allocation, the same-lineage
        duplicate check, the repository insert, and the latest-pointer update
        all happen in one transaction, so a partial allocation can never be
        observed or committed.

        Raises ``LineageDuplicateRevision`` (not retried) if this exact commit
        already exists in the target lineage.
        """
        if canonical_source_key is None:
            return self.add(record)

        last_error: IntegrityError | None = None
        for _ in range(_MAX_LINEAGE_RETRIES):
            try:
                return self._add_with_lineage_once(
                    record,
                    owner_id=owner_id,
                    canonical_source_key=canonical_source_key,
                    canonical_branch=canonical_branch,
                    display_name=display_name,
                )
            except IntegrityError as exc:
                last_error = exc
                self.db.rollback()
        assert last_error is not None
        raise last_error

    def _find_lineage(
        self, owner_id: str, canonical_source_key: str, canonical_branch: str | None
    ) -> RepositoryLineage | None:
        statement = select(RepositoryLineage).where(
            RepositoryLineage.owner_id == owner_id,
            RepositoryLineage.canonical_source_key == canonical_source_key,
            RepositoryLineage.canonical_branch == canonical_branch,
        )
        return self.db.scalars(statement).first()

    def _add_with_lineage_once(
        self,
        record: RepositoryRecord,
        *,
        owner_id: str,
        canonical_source_key: str,
        canonical_branch: str | None,
        display_name: str,
    ) -> RepositoryRecord:
        lineage = self._find_lineage(owner_id, canonical_source_key, canonical_branch)
        if lineage is None:
            lineage = RepositoryLineage(
                id=str(uuid4()),
                owner_id=owner_id,
                canonical_source_key=canonical_source_key,
                canonical_branch=canonical_branch,
                display_name=display_name,
                latest_repository_id=None,
                next_sequence=1,
                created_at=datetime.now(UTC),
            )
            self.db.add(lineage)
            # Flush (not commit) so a racing winner's canonical unique index
            # raises IntegrityError here, before this transaction allocates a
            # sequence for a lineage that turns out not to be the real one.
            self.db.flush()

        # Atomic, race-free allocation (RFC §5.1): the write lock this UPDATE
        # takes is held through commit on both dialects, so two concurrent
        # allocations against the same lineage always serialize here rather
        # than both reading the same `next_sequence`.
        result = self.db.execute(
            update(RepositoryLineage)
            .where(RepositoryLineage.id == lineage.id, RepositoryLineage.owner_id == owner_id)
            .values(next_sequence=RepositoryLineage.next_sequence + 1)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            # Unreachable except as a defensive guard: the lineage was just
            # selected or inserted in this same transaction and cannot vanish
            # underneath it (deletion of an in-flight, uncommitted lineage is
            # not possible from another connection).
            raise RuntimeError("Repository lineage row vanished during sequence allocation.")
        self.db.refresh(lineage)
        allocated_sequence = lineage.next_sequence - 1

        existing = self.db.scalars(
            select(RepositoryRecord).where(
                RepositoryRecord.lineage_id == lineage.id,
                RepositoryRecord.revision_value == record.revision_value,
            )
        ).first()
        if existing is not None:
            self.db.rollback()
            raise LineageDuplicateRevision(existing)

        record.lineage_id = lineage.id
        record.sequence = allocated_sequence
        self.db.add(record)
        self.db.flush()

        lineage.latest_repository_id = record.id
        self.db.commit()
        self.db.refresh(record)
        return record
