from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import RepositoryRecord


class RepositoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[RepositoryRecord]:
        statement = select(RepositoryRecord).order_by(RepositoryRecord.uploaded_at.desc())
        return list(self.db.scalars(statement).all())

    def get(self, repository_id: str) -> RepositoryRecord | None:
        return self.db.get(RepositoryRecord, repository_id)

    def find_by_name(self, name: str) -> RepositoryRecord | None:
        statement = select(RepositoryRecord).where(RepositoryRecord.name == name)
        return self.db.scalars(statement).first()

    def find_by_source(self, source_url: str, branch: str | None) -> RepositoryRecord | None:
        statement = select(RepositoryRecord).where(
            RepositoryRecord.source_url == source_url,
            RepositoryRecord.branch == branch,
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
