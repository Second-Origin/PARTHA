from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.core.exceptions import ConflictServiceError, NotFoundError
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.analysis_job import AnalysisJob
from app.models.base import Base
from app.models.snapshot import RiSnapshot
from app.services.analysis_job_service import (
    ANALYSIS_CONFIG_HASH,
    ANALYSIS_PRODUCER_VERSION_SET,
    ANALYSIS_SCHEMA_VERSION,
    AnalysisJobService,
)

UPLOAD_REVISION = "sha256:" + "b" * 64


@pytest.fixture()
def session_factory(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _owner(session) -> User:
    owner = User(id=str(uuid4()), email=f"{uuid4().hex}@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    return owner


def _repository(session, owner: User) -> RepositoryRecord:
    record = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name="repo",
        source="upload",
        revision_kind="upload",
        revision_value=UPLOAD_REVISION,
        local_path="/x",
        status="analysing",
        file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def _seal_minimal_snapshot(session, record: RepositoryRecord) -> RiSnapshot:
    """Seal a completed snapshot carrying the exact analysis identity."""

    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=record.id,
        revision=Revision(record.revision_kind, record.revision_value, record.revision_ref),
        producer_version_set=ANALYSIS_PRODUCER_VERSION_SET,
        config_hash=ANALYSIS_CONFIG_HASH,
    )
    store.add_node(
        snapshot,
        node_kind="repository",
        stable_key="repo:root",
        evidence=[
            Evidence(
                path="README.md",
                start_line=1,
                end_line=1,
                extractor="repository-inventory",
                extractor_version="1.0.0",
                logical_line_count=1,
                granularity="file",
            )
        ],
    )
    return store.seal(snapshot)


def test_submit_enqueues_a_queued_job(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)

        job = service.submit(record.id)

        assert job.status == "queued"
        assert job.attempt == 0
        assert job.repository_id == record.id
        assert job.config_hash == ANALYSIS_CONFIG_HASH
        assert job.revision_value == UPLOAD_REVISION


def test_submit_is_idempotent_for_an_active_job(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)

        first = service.submit(record.id)
        second = service.submit(record.id)

        assert first.id == second.id
        with session_factory() as reader:
            count = reader.scalar(
                select(func.count()).select_from(AnalysisJob).where(AnalysisJob.repository_id == record.id)
            )
        assert count == 1


def test_concurrent_submit_race_reconciles_to_one_job(session_factory):
    # Simulate two racing submits: both prechecks miss the active row, both try
    # to insert, and the partial unique index rejects the loser — whose service
    # must re-read and return the winner rather than error.
    with session_factory() as bootstrap:
        owner = _owner(bootstrap)
        record = _repository(bootstrap, owner)
        owner_id = owner.id
        record_id = record.id

    session_a = session_factory()
    session_b = session_factory()
    try:
        service_a = AnalysisJobService(session_a, owner_id)
        service_b = AnalysisJobService(session_b, owner_id)

        record_b = service_b.repository.get_for_owner(record_id, owner_id)
        # B's precheck sees no active job yet.
        assert service_b._active_job(record_id, ANALYSIS_CONFIG_HASH) is None

        # A wins the race and commits its queued job.
        job_a = service_a.submit(record_id)

        # B's insert now collides on the active-identity index and reconciles.
        job_b = service_b._insert_queued_job(record_b, ANALYSIS_CONFIG_HASH)
        assert job_b.id == job_a.id
    finally:
        session_a.close()
        session_b.close()

    with session_factory() as reader:
        count = reader.scalar(
            select(func.count()).select_from(AnalysisJob).where(AnalysisJob.repository_id == record_id)
        )
    assert count == 1


def test_submit_short_circuits_when_a_completed_snapshot_exists(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        snapshot = _seal_minimal_snapshot(session, record)

        before = session.scalar(select(func.count()).select_from(RiSnapshot))
        service = AnalysisJobService(session, owner.id)
        job = service.submit(record.id)

        assert job.status == "completed"
        assert job.snapshot_id == snapshot.snapshot_id
        assert job.progress == 100
        # No new snapshot work was created.
        after = session.scalar(select(func.count()).select_from(RiSnapshot))
        assert after == before == 1


def test_submit_reuses_the_synthesized_completed_job(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        _seal_minimal_snapshot(session, record)
        service = AnalysisJobService(session, owner.id)

        first = service.submit(record.id)
        second = service.submit(record.id)

        assert first.id == second.id
        count = session.scalar(
            select(func.count()).select_from(AnalysisJob).where(AnalysisJob.repository_id == record.id)
        )
        assert count == 1


def test_status_returns_none_before_any_submission(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)

        assert service.status(record.id) is None


def test_status_returns_the_most_recent_job(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)
        job = service.submit(record.id)

        assert service.status(record.id).id == job.id


def test_cancel_queued_job_transitions_to_cancelled(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)
        service.submit(record.id)

        cancelled = service.cancel(record.id)
        assert cancelled.status == "cancelled"


def test_cancel_running_job_sets_cancel_requested(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)
        job = service.submit(record.id)
        job.status = "running"
        session.commit()

        result = service.cancel(record.id)
        assert result.status == "running"
        assert result.cancel_requested is True


def test_cancel_terminal_job_conflicts(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)
        job = service.submit(record.id)
        job.status = "completed"
        session.commit()

        with pytest.raises(ConflictServiceError):
            service.cancel(record.id)


def test_cancel_without_a_job_conflicts(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)

        with pytest.raises(ConflictServiceError):
            service.cancel(record.id)


def test_submit_unknown_repository_is_not_found(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        service = AnalysisJobService(session, owner.id)

        with pytest.raises(NotFoundError):
            service.submit(str(uuid4()))


def test_submit_cross_owner_repository_is_not_found(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        other = _owner(session)
        service = AnalysisJobService(session, other.id)

        with pytest.raises(NotFoundError):
            service.submit(record.id)
