"""Test analysis_job model and constraints."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.models import AnalysisJob, RepositoryRecord, User
from app.models.base import Base


@pytest.fixture()
def db(tmp_path):
    """Create in-memory SQLite database with FK enforcement for tests."""
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'analysis_jobs.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session, factory
    engine.dispose()


def _owner(session: Session, email: str = "owner@example.com") -> User:
    """Create and return a test user."""
    owner = User(id=str(uuid4()), email=email, password_hash=None)
    session.add(owner)
    session.commit()
    return owner


def _repository(session: Session, owner: User) -> RepositoryRecord:
    """Create and return a test repository."""
    record = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name=f"repo-{uuid4().hex[:6]}",
        source="upload",
        source_url=None,
        branch=None,
        revision_kind="upload",
        revision_value="sha256:" + "a" * 64,
        revision_ref=None,
        local_path="/stored/revision",
        status="completed",
        repo_metadata={},
        file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def test_analysis_job_table_exists(db):
    """Verify the analysis_jobs table can be created."""
    session, _ = db
    # If Base.metadata.create_all succeeded, the table exists.
    # Verify by querying it.
    result = session.execute(select(AnalysisJob)).scalars().all()
    assert result == []


def test_analysis_job_basic_insert(db):
    """Verify basic analysis job insertion."""
    session, _ = db
    owner = _owner(session)
    repo = _repository(session, owner)

    job = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash="sha256:" + "b" * 64,
        status="queued",
    )
    session.add(job)
    session.commit()

    # Verify it was inserted
    result = session.execute(
        select(AnalysisJob).where(AnalysisJob.id == job.id)
    ).scalar_one()
    assert result.status == "queued"
    assert result.progress == 0
    assert result.attempt == 0
    assert result.max_attempts == 3


def test_analysis_job_status_constraint_valid(db):
    """Verify valid status values are accepted."""
    session, _ = db
    owner = _owner(session)

    for status in ["queued", "running", "completed", "failed", "cancelled"]:
        # Create a new repo for each status to avoid partial unique index conflicts
        repo = _repository(session, owner)
        job = AnalysisJob(
            id=str(uuid4()),
            repository_id=repo.id,
            owner_id=owner.id,
            revision_kind="upload",
            revision_value=repo.revision_value,
            config_hash="sha256:" + "b" * 64,
            status=status,
        )
        session.add(job)
        session.commit()

        # Verify it was inserted
        result = session.execute(
            select(AnalysisJob).where(AnalysisJob.id == job.id)
        ).scalar_one()
        assert result.status == status


def test_analysis_job_status_constraint_invalid(db):
    """Verify invalid status values are rejected by CheckConstraint."""
    session, _ = db
    owner = _owner(session)
    repo = _repository(session, owner)

    job = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash="sha256:" + "b" * 64,
        status="invalid_status",
    )
    session.add(job)

    # CheckConstraint should reject this
    with pytest.raises(IntegrityError):
        session.commit()


def test_analysis_job_partial_unique_index_queued_duplicate_rejected(db):
    """Verify partial unique index rejects duplicate queued jobs for same identity."""
    session, _ = db
    owner = _owner(session)
    repo = _repository(session, owner)

    config_hash = "sha256:" + "b" * 64

    # Insert first queued job
    job1 = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash=config_hash,
        status="queued",
    )
    session.add(job1)
    session.commit()

    # Try to insert second queued job with same (repository_id, revision_value, config_hash)
    job2 = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash=config_hash,
        status="queued",
    )
    session.add(job2)

    # Should reject due to partial unique index
    with pytest.raises(IntegrityError):
        session.commit()


def test_analysis_job_partial_unique_index_completed_allowed(db):
    """Verify partial unique index allows second completed job for same identity."""
    session, _ = db
    owner = _owner(session)
    repo = _repository(session, owner)

    config_hash = "sha256:" + "b" * 64
    now = datetime.now(UTC)

    # Insert first completed job
    job1 = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash=config_hash,
        status="completed",
        completed_at=now,
    )
    session.add(job1)
    session.commit()

    # Insert second completed job with same identity - should succeed
    job2 = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash=config_hash,
        status="completed",
        completed_at=now,
    )
    session.add(job2)
    session.commit()

    # Verify both were inserted
    results = session.execute(
        select(AnalysisJob)
        .where(AnalysisJob.config_hash == config_hash)
        .where(AnalysisJob.status == "completed")
    ).scalars().all()
    assert len(results) == 2


def test_analysis_job_partial_unique_index_mixed_states_allowed(db):
    """Verify partial unique index allows queued + completed for same identity."""
    session, _ = db
    owner = _owner(session)
    repo = _repository(session, owner)

    config_hash = "sha256:" + "b" * 64
    now = datetime.now(UTC)

    # Insert queued job
    job1 = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash=config_hash,
        status="queued",
    )
    session.add(job1)
    session.commit()

    # Insert completed job with same identity - should succeed
    # (only queued/running are constrained)
    job2 = AnalysisJob(
        id=str(uuid4()),
        repository_id=repo.id,
        owner_id=owner.id,
        revision_kind="upload",
        revision_value=repo.revision_value,
        config_hash=config_hash,
        status="completed",
        completed_at=now,
    )
    session.add(job2)
    session.commit()

    # Verify both were inserted
    results = session.execute(
        select(AnalysisJob).where(AnalysisJob.config_hash == config_hash)
    ).scalars().all()
    assert len(results) == 2
    assert any(j.status == "queued" for j in results)
    assert any(j.status == "completed" for j in results)
