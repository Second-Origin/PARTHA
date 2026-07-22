from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.intelligence.query_service import SnapshotQueryService
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.analysis_job import AnalysisJob
from app.models.base import Base
from app.models.snapshot import RiSnapshot
from app.schemas.repository import RepositoryMeta
from app.services.analysis_job_service import (
    ANALYSIS_CONFIG_HASH,
    ANALYSIS_PRODUCER_VERSION_SET,
    AnalysisJobService,
)
from app.workers.analysis_worker import AnalysisWorker

UPLOAD_REVISION = "sha256:" + "d" * 64


@pytest.fixture()
def session_factory(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _owner(session) -> User:
    owner = User(id=str(uuid4()), email=f"{uuid4().hex}@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    return owner


def _meta() -> dict:
    return RepositoryMeta(
        language="Python",
        framework="FastAPI",
        total_files=2,
        total_folders=1,
        entry_point="app/main.py",
        config_files=[],
        package_manager=None,
        has_readme=True,
        has_license=False,
        license_name=None,
    ).model_dump(mode="json", by_alias=True)


def _repository_with_sources(session, owner: User, root: Path) -> RepositoryRecord:
    """Create a repository whose files exist on disk, ready for real extraction."""

    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Worker fixture\n", encoding="utf-8")
    (root / "app").mkdir(exist_ok=True)
    (root / "app" / "main.py").write_text("def handler():\n    return 1\n", encoding="utf-8")

    file_tree = [
        {"id": "1", "name": "README.md", "type": "file", "path": "README.md", "size": 18, "extension": "md"},
        {
            "id": "2",
            "name": "app",
            "type": "folder",
            "path": "app",
            "children": [
                {
                    "id": "3",
                    "name": "main.py",
                    "type": "file",
                    "path": "app/main.py",
                    "size": 28,
                    "extension": "py",
                    "language": "python",
                }
            ],
        },
    ]
    record = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name="repo",
        source="upload",
        revision_kind="upload",
        revision_value=UPLOAD_REVISION,
        local_path=str(root),
        status="analysing",
        file_tree=file_tree,
        repo_metadata=_meta(),
    )
    session.add(record)
    session.commit()
    return record


def _seal_analysis_snapshot(session, record: RepositoryRecord) -> RiSnapshot:
    """Seal a completed snapshot carrying the exact analysis semantic identity."""

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


def test_run_once_returns_false_when_queue_is_empty(session_factory):
    worker = AnalysisWorker(session_factory, worker_id="w", lease_seconds=60)
    assert worker.run_once() is False


def test_run_once_executes_end_to_end_and_seals_a_readable_snapshot(session_factory, tmp_path):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository_with_sources(session, owner, tmp_path / "repo")
        owner_id = owner.id
        record_id = record.id
        AnalysisJobService(session, owner_id).submit(record_id)

    worker = AnalysisWorker(session_factory, worker_id="w", lease_seconds=60)
    assert worker.run_once() is True
    # Queue is now drained.
    assert worker.run_once() is False

    with session_factory() as session:
        job = session.scalars(select(AnalysisJob).where(AnalysisJob.repository_id == record_id)).one()
        assert job.status == "completed"
        assert job.progress == 100
        assert job.stage == "completed"
        assert job.snapshot_id is not None
        assert job.completed_at is not None
        assert job.worker_id is None

        record = session.get(RepositoryRecord, record_id)
        assert record.status == "completed"
        assert record.analysis_stage == "completed"
        assert record.analysis_progress == 100
        assert record.analysed_at is not None

        # The whole point of #93: a real product-ingested snapshot now exists and
        # is readable through the owner-scoped query service.
        query = SnapshotQueryService(session, owner_id)
        snapshot = query.metadata(job.snapshot_id)
        assert snapshot.state == "completed"
        _, symbols, total = query.symbols(job.snapshot_id, offset=0, limit=50)
        assert total >= 1
        assert any(node.name == "handler" for node in symbols)


def test_run_once_reuses_an_already_sealed_snapshot(session_factory, tmp_path):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository_with_sources(session, owner, tmp_path / "repo")
        snapshot = _seal_analysis_snapshot(session, record)
        reused_id = snapshot.snapshot_id
        record_id = record.id
        # Insert a queued job directly for the same identity (bypassing submit's
        # completed-snapshot short-circuit) to exercise the worker's reuse branch.
        session.add(
            AnalysisJob(
                id=str(uuid4()),
                repository_id=record.id,
                owner_id=owner.id,
                revision_kind=record.revision_kind,
                revision_value=record.revision_value,
                config_hash=ANALYSIS_CONFIG_HASH,
                status="queued",
                attempt=0,
            )
        )
        session.commit()
        before = session.scalar(select(func.count()).select_from(RiSnapshot))

    worker = AnalysisWorker(session_factory, worker_id="w", lease_seconds=60)
    assert worker.run_once() is True

    with session_factory() as session:
        job = session.scalars(select(AnalysisJob).where(AnalysisJob.repository_id == record_id)).one()
        assert job.status == "completed"
        assert job.snapshot_id == reused_id
        # No new snapshot work was created.
        after = session.scalar(select(func.count()).select_from(RiSnapshot))
        assert after == before == 1


def test_bounded_retry_requeues_with_backoff_then_fails(session_factory, tmp_path, monkeypatch):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository_with_sources(session, owner, tmp_path / "repo")
        record_id = record.id
        AnalysisJobService(session, owner.id).submit(record_id)

    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    worker = AnalysisWorker(session_factory, worker_id="w", lease_seconds=60, clock=lambda: now[0])

    def _boom(ctx):
        raise RuntimeError("stage exploded")

    monkeypatch.setattr(worker, "_stage_legacy", _boom)

    # Attempt 1: fails, re-queued with a future next_attempt_at.
    assert worker.run_once() is True
    with session_factory() as session:
        job = session.scalars(select(AnalysisJob).where(AnalysisJob.repository_id == record_id)).one()
        assert job.status == "queued"
        assert job.attempt == 1
        assert job.next_attempt_at is not None
        assert job.error_message == "stage exploded"

    # The backoff is in the future, so the job is not yet claimable.
    assert worker.run_once() is False

    # Advance past the backoff: attempt 2 fails and re-queues again.
    now[0] = now[0] + timedelta(seconds=120)
    assert worker.run_once() is True
    with session_factory() as session:
        job = session.scalars(select(AnalysisJob).where(AnalysisJob.repository_id == record_id)).one()
        assert job.status == "queued"
        assert job.attempt == 2

    # Attempt 3 reaches max_attempts (default 3): terminal failure, never retries again.
    now[0] = now[0] + timedelta(seconds=120)
    assert worker.run_once() is True
    with session_factory() as session:
        job = session.scalars(select(AnalysisJob).where(AnalysisJob.repository_id == record_id)).one()
        assert job.status == "failed"
        assert job.attempt == 3
        assert job.error_message == "stage exploded"
        record = session.get(RepositoryRecord, record_id)
        assert record.status == "error"
        assert record.error_message == "Repository analysis failed."

    now[0] = now[0] + timedelta(seconds=120)
    assert worker.run_once() is False


def test_cooperative_cancellation_fails_open_snapshot_and_cancels_job(session_factory, tmp_path):
    session = session_factory()
    try:
        owner = _owner(session)
        record = _repository_with_sources(session, owner, tmp_path / "repo")
        service = AnalysisJobService(session, owner.id)
        service.submit(record.id)

        worker = AnalysisWorker(session_factory, worker_id="w", lease_seconds=60)
        job = worker._claim(session)
        assert job is not None

        stages = worker._execute_stages(session, job)
        next(stages)  # legacy stage completes
        next(stages)  # snapshot opened (building) — id recorded before sealing
        snapshot_id = job.snapshot_id
        assert snapshot_id is not None
        assert session.get(RiSnapshot, snapshot_id).state == "building"

        # Cancel mid-run: the running job is flagged, and the worker observes it
        # at the next stage boundary.
        service.cancel(record.id)

        list(stages)  # drain remaining boundaries; the cancel is honoured

        session.expire_all()
        cancelled = session.get(AnalysisJob, job.id)
        assert cancelled.status == "cancelled"
        assert cancelled.completed_at is not None
        # The opened snapshot was failed, never sealed to completed.
        assert session.get(RiSnapshot, snapshot_id).state == "failed"
    finally:
        session.close()
