from __future__ import annotations

import os
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
from app.workers.analysis_worker import AnalysisWorker, _StageContext

UPLOAD_REVISION = "sha256:" + "b" * 64
PG_URL = os.environ.get("PARTHA_TEST_PG_URL")


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


def _assert_submit_reconciles_worker_completion(factory) -> None:
    with factory() as bootstrap:
        owner = _owner(bootstrap)
        record = _repository(bootstrap, owner)
        owner_id = owner.id
        record_id = record.id
        original = AnalysisJobService(bootstrap, owner_id).submit(record_id)

    submit_session = factory()
    worker_session = factory()
    try:
        submitting = AnalysisJobService(submit_session, owner_id)
        submit_record = submitting.repository.get_for_owner(record_id, owner_id)

        # 1. The submission's first completed-snapshot observation misses.
        assert submitting._completed_snapshot(submit_record, UPLOAD_REVISION) is None

        # 2. The existing worker seals and completes in a separate transaction.
        worker = AnalysisWorker(factory, worker_id="worker-a", lease_seconds=60)
        claimed = worker._claim(worker_session)
        assert claimed is not None and claimed.id == original.id
        worker_record = worker_session.get(RepositoryRecord, record_id)
        snapshot = _seal_minimal_snapshot(worker_session, worker_record)
        claimed.snapshot_id = snapshot.snapshot_id
        ctx = _StageContext(session=worker_session, job=claimed, record=worker_record)
        worker._checkpoint(ctx, "preparing-architecture", 90)
        worker._complete(ctx)

        # 3. The stale submission misses active work and attempts its INSERT.
        assert submitting._active_job(record_id, ANALYSIS_CONFIG_HASH) is None
        reconciled = submitting._insert_queued_job(submit_record, ANALYSIS_CONFIG_HASH)

        # 4. The effective-identity constraint returns the committed winner.
        assert reconciled.id == original.id
        assert reconciled.status == "completed"
        assert submitting.status(record_id).id == original.id
        assert submitting.status(record_id).status == "completed"
    finally:
        submit_session.close()
        worker_session.close()

    with factory() as reader:
        jobs = reader.scalars(
            select(AnalysisJob).where(AnalysisJob.repository_id == record_id)
        ).all()
        assert len(jobs) == 1
        assert jobs[0].status == "completed"
        assert jobs[0].snapshot_id is not None
        assert reader.scalar(
            select(func.count())
            .select_from(RiSnapshot)
            .where(
                RiSnapshot.repository_id == record_id,
                RiSnapshot.state == "completed",
            )
        ) == 1


def test_submit_is_atomic_against_worker_completion(session_factory):
    _assert_submit_reconciles_worker_completion(session_factory)


@pytest.mark.skipif(not PG_URL, reason="set PARTHA_TEST_PG_URL to run the Postgres concurrency test")
def test_submit_is_atomic_against_worker_completion_on_postgres():
    engine = create_engine(PG_URL)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        _assert_submit_reconciles_worker_completion(factory)
    finally:
        engine.dispose()


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


def test_concurrent_completed_snapshot_submits_reconcile_to_one_job(session_factory):
    with session_factory() as bootstrap:
        owner = _owner(bootstrap)
        record = _repository(bootstrap, owner)
        snapshot = _seal_minimal_snapshot(bootstrap, record)
        owner_id = owner.id
        record_id = record.id
        snapshot_id = snapshot.snapshot_id

    session_a = session_factory()
    session_b = session_factory()
    try:
        service_a = AnalysisJobService(session_a, owner_id)
        service_b = AnalysisJobService(session_b, owner_id)
        record_a = service_a.repository.get_for_owner(record_id, owner_id)
        record_b = service_b.repository.get_for_owner(record_id, owner_id)
        snapshot_a = session_a.get(RiSnapshot, snapshot_id)
        snapshot_b = session_b.get(RiSnapshot, snapshot_id)

        # Both callers complete the initial lookup before either inserts.
        assert service_a._job_for_snapshot(record_id, snapshot_id) is None
        assert service_b._job_for_snapshot(record_id, snapshot_id) is None

        winner = service_a._insert_completed_job(record_a, snapshot_a)
        reconciled = service_b._insert_completed_job(record_b, snapshot_b)

        assert reconciled.id == winner.id
    finally:
        session_a.close()
        session_b.close()

    with session_factory() as reader:
        jobs = reader.scalars(
            select(AnalysisJob).where(AnalysisJob.snapshot_id == snapshot_id)
        ).all()
        assert len(jobs) == 1
        assert jobs[0].status == "completed"
        assert reader.scalar(select(func.count()).select_from(RiSnapshot)) == 1


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


def test_status_prefers_the_completed_snapshot_over_a_newer_failed_attempt(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        _seal_minimal_snapshot(session, record)
        service = AnalysisJobService(session, owner.id)
        completed = service.submit(record.id)
        session.add(
            AnalysisJob(
                id=str(uuid4()),
                repository_id=record.id,
                owner_id=owner.id,
                revision_kind=record.revision_kind,
                revision_value=record.revision_value,
                config_hash=ANALYSIS_CONFIG_HASH,
                status="failed",
                completed_at=completed.completed_at,
            )
        )
        session.commit()

        authoritative = service.status(record.id)

        assert authoritative.id == completed.id
        assert authoritative.status == "completed"


def test_cancel_queued_job_transitions_to_cancelled(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)
        service.submit(record.id)

        cancelled = service.cancel(record.id)
        assert cancelled.status == "cancelled"
        assert cancelled.worker_id is None
        assert cancelled.lease_expires_at is None
        session.refresh(record)
        assert record.status == "cancelled"
        assert record.analysis_stage is None
        assert record.analysis_progress == 0


def test_cancelled_job_can_be_restarted_without_reupload(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        service = AnalysisJobService(session, owner.id)
        service.submit(record.id)
        cancelled = service.cancel(record.id)

        restarted = service.submit(record.id)

        assert cancelled.status == "cancelled"
        assert restarted.status == "queued"
        assert restarted.id != cancelled.id
        session.refresh(record)
        assert record.status == "analysing"
        assert record.analysis_progress == 0


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


def test_cancel_reconciles_a_queued_to_running_claim_race(session_factory):
    with session_factory() as bootstrap:
        owner = _owner(bootstrap)
        record = _repository(bootstrap, owner)
        owner_id = owner.id
        record_id = record.id
        AnalysisJobService(bootstrap, owner_id).submit(record_id)

    cancel_session = session_factory()
    worker_session = session_factory()
    try:
        service = AnalysisJobService(cancel_session, owner_id)
        stale_queued = service._latest_job(record_id)
        assert stale_queued.status == "queued"

        worker = AnalysisWorker(session_factory, worker_id="worker-a", lease_seconds=60)
        claimed = worker._claim(worker_session)
        assert claimed is not None
        assert claimed.worker_id == "worker-a"

        cancellation = service._cancel_job(stale_queued)
        assert cancellation.status == "running"
        assert cancellation.cancel_requested is True
        assert cancellation.worker_id == "worker-a"
        assert cancellation.lease_expires_at is not None

        list(worker._execute_stages(worker_session, claimed))
    finally:
        cancel_session.close()
        worker_session.close()

    with session_factory() as reader:
        job = reader.scalars(
            select(AnalysisJob).where(AnalysisJob.repository_id == record_id)
        ).one()
        assert job.status == "cancelled"
        assert job.worker_id is None
        assert job.lease_expires_at is None
        assert reader.scalar(select(func.count()).select_from(RiSnapshot)) == 0


def test_cancel_does_not_overwrite_a_worker_completion_race(session_factory):
    with session_factory() as bootstrap:
        owner = _owner(bootstrap)
        record = _repository(bootstrap, owner)
        owner_id = owner.id
        record_id = record.id
        AnalysisJobService(bootstrap, owner_id).submit(record_id)

    cancel_session = session_factory()
    worker_session = session_factory()
    try:
        worker = AnalysisWorker(session_factory, worker_id="worker-a", lease_seconds=60)
        claimed = worker._claim(worker_session)
        assert claimed is not None

        service = AnalysisJobService(cancel_session, owner_id)
        stale_running = service._latest_job(record_id)
        assert stale_running.status == "running"

        worker._complete(
            _StageContext(
                session=worker_session,
                job=claimed,
                record=worker_session.get(RepositoryRecord, record_id),
            )
        )

        with pytest.raises(ConflictServiceError):
            service._cancel_job(stale_running)
    finally:
        cancel_session.close()
        worker_session.close()

    with session_factory() as reader:
        job = reader.scalars(
            select(AnalysisJob).where(AnalysisJob.repository_id == record_id)
        ).one()
        assert job.status == "completed"
        assert job.cancel_requested is False
        assert job.worker_id is None
        assert job.lease_expires_at is None


def test_accepted_cancel_wins_after_the_workers_final_cancel_check(session_factory):
    with session_factory() as bootstrap:
        owner = _owner(bootstrap)
        record = _repository(bootstrap, owner)
        owner_id = owner.id
        record_id = record.id
        AnalysisJobService(bootstrap, owner_id).submit(record_id)

    worker_session = session_factory()
    cancel_session = session_factory()
    try:
        worker = AnalysisWorker(session_factory, worker_id="worker-a", lease_seconds=60)
        claimed = worker._claim(worker_session)
        assert claimed is not None
        ctx = _StageContext(
            session=worker_session,
            job=claimed,
            record=worker_session.get(RepositoryRecord, record_id),
        )

        # Exact ordering: the worker's final cooperative read sees false, then
        # cancellation commits before the completion CAS executes.
        assert worker._cancel_requested(ctx) is False
        cancellation = AnalysisJobService(cancel_session, owner_id).cancel(record_id)
        assert cancellation.status == "running"
        assert cancellation.cancel_requested is True

        worker._complete(ctx)
    finally:
        worker_session.close()
        cancel_session.close()

    with session_factory() as reader:
        job = reader.scalars(
            select(AnalysisJob).where(AnalysisJob.repository_id == record_id)
        ).one()
        assert job.status == "cancelled"
        assert job.completed_at is not None
        assert job.worker_id is None
        assert job.lease_expires_at is None
        assert reader.scalar(select(func.count()).select_from(RiSnapshot)) == 0


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
