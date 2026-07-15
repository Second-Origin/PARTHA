from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import RepositoryRecord


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

    def find_by_name_for_owner(self, name: str, owner_id: str) -> RepositoryRecord | None:
        statement = select(RepositoryRecord).where(
            RepositoryRecord.name == name,
            RepositoryRecord.owner_id == owner_id,
        )
        return self.db.scalars(statement).first()

    def find_by_source_for_owner(self, source_url: str, branch: str | None, owner_id: str) -> RepositoryRecord | None:
        statement = select(RepositoryRecord).where(
            RepositoryRecord.source_url == source_url,
            RepositoryRecord.branch == branch,
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
