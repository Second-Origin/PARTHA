"""The analysis queue and control-plane boundary (#324).

These tests exercise ``app.workers.control_plane`` and ``app.workers.runner``
directly, without running the extraction pipeline: the point is *who owns a
job*, not what analysing it produces. Pipeline behaviour is already covered by
``test_analysis_worker.py``, and this file must not become a second copy of it.

Determinism: every race here is expressed as an explicit interleaving (both
sides read, then both sides write) or synchronised with a ``threading.Barrier``.
Nothing sleeps waiting for a race to happen, so a slow machine cannot turn a
correctness assertion into a flake. The one genuinely threaded race is gated on
a real PostgreSQL server, matching the repository's established pattern for
concurrency that SQLite's single-writer lock cannot represent.
"""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.models import RepositoryRecord, User
from app.models.analysis_job import AnalysisJob
from app.models.base import Base
from app.services.analysis_job_service import ANALYSIS_CONFIG_HASH
from app.workers.control_plane import (
    DatabaseAnalysisControlPlane,
    JobLease,
    lease_expired,
)
from app.workers.runner import AnalysisWorkerRunner, new_worker_id

UPLOAD_REVISION = "sha256:" + "c" * 64
PG_URL = os.environ.get("PARTHA_TEST_PG_URL")


@pytest.fixture()
def session_factory(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'control-plane.db'}")
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


def _queued_job(session, record: RepositoryRecord, **overrides) -> AnalysisJob:
    """Insert a queued job row directly -- the queue's input, not the pipeline's."""

    values: dict[str, object] = {
        "id": str(uuid4()),
        "repository_id": record.id,
        "owner_id": record.owner_id,
        "revision_kind": record.revision_kind,
        "revision_value": record.revision_value,
        "config_hash": ANALYSIS_CONFIG_HASH,
        "status": "queued",
        "attempt": 0,
    }
    values.update(overrides)
    job = AnalysisJob(**values)
    session.add(job)
    session.commit()
    return job


def _bootstrap(factory, **overrides) -> tuple[str, str]:
    """Create one owner, repository and queued job; return (record_id, job_id)."""

    with factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        job = _queued_job(session, record, **overrides)
        return record.id, job.id


def _plane(lease_seconds: int = 60, clock=None) -> DatabaseAnalysisControlPlane:
    if clock is None:
        return DatabaseAnalysisControlPlane(lease_seconds=lease_seconds)
    return DatabaseAnalysisControlPlane(lease_seconds=lease_seconds, clock=clock)


# -- AC1: jobs are claimed through an explicit lease path --------------------


def test_claim_returns_a_lease_and_marks_the_job_running(session_factory):
    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        lease = plane.claim(session, worker_id="worker-a")

    assert lease is not None
    assert lease.job_id == job_id
    assert lease.worker_id == "worker-a"
    assert lease.attempt == 1

    with session_factory() as reader:
        job = reader.get(AnalysisJob, job_id)
        assert job.status == "running"
        assert job.worker_id == "worker-a"
        assert job.lease_expires_at is not None
        assert job.started_at is not None
        assert job.next_attempt_at is None


def test_claim_returns_none_when_the_queue_is_empty(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        _repository(session, owner)

    with session_factory() as session:
        assert _plane().claim(session, worker_id="worker-a") is None


def test_claim_skips_a_job_still_serving_retry_backoff(session_factory):
    """``next_attempt_at`` is queue eligibility, not just a record of intent."""

    future = datetime.now(UTC) + timedelta(seconds=300)
    _, job_id = _bootstrap(session_factory, next_attempt_at=future)
    plane = _plane()

    with session_factory() as session:
        assert plane.claim(session, worker_id="worker-a") is None

    # Once the delay elapses the same job becomes claimable, unchanged.
    later = _plane(clock=lambda: datetime.now(UTC) + timedelta(seconds=600))
    with session_factory() as session:
        lease = later.claim(session, worker_id="worker-a")
    assert lease is not None and lease.job_id == job_id


def test_claim_takes_the_oldest_eligible_job_first(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        record = _repository(session, owner)
        older = _queued_job(session, record, created_at=datetime.now(UTC) - timedelta(minutes=5))
        # A second repository, because one repository may hold only one
        # effective-identity job at a time.
        other_record = _repository(session, owner)
        _queued_job(session, other_record, created_at=datetime.now(UTC))
        older_id = older.id

    with session_factory() as session:
        lease = _plane().claim(session, worker_id="worker-a")

    assert lease is not None and lease.job_id == older_id


# -- AC2: duplicate claims and expired leases --------------------------------


class _PinnedCandidatePlane(DatabaseAnalysisControlPlane):
    """A control plane frozen just after it read its candidate.

    A claim is a candidate read followed by a compare-and-swap. The loser of a
    real race is a worker whose read happened *before* the winner committed, so
    reproducing the race means holding that stale candidate across the winner's
    claim. Pinning the id does exactly that and changes nothing else: the swap
    under test is the unmodified production statement.
    """

    def __init__(self, candidate_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._candidate_id = candidate_id

    def next_eligible_job_id(self, session, *, now=None):
        return self._candidate_id


def test_two_workers_racing_one_job_produce_exactly_one_owner(session_factory):
    """The claim guard, proved by an explicit interleaving.

    Both workers resolve the same candidate before either swaps, which is
    precisely the window a ``SELECT`` then ``UPDATE`` claim has to survive. The
    ``status='queued'`` predicate is what makes the loser's write match no row.
    """

    _, job_id = _bootstrap(session_factory)

    session_a = session_factory()
    session_b = session_factory()
    try:
        # Both read the queue while the job is still queued.
        candidate_a = _plane().next_eligible_job_id(session_a)
        candidate_b = _plane().next_eligible_job_id(session_b)
        assert candidate_a == candidate_b == job_id

        # Both now swap, each still holding the candidate it read.
        lease_a = _PinnedCandidatePlane(candidate_a, lease_seconds=60).claim(session_a, worker_id="worker-a")
        lease_b = _PinnedCandidatePlane(candidate_b, lease_seconds=60).claim(session_b, worker_id="worker-b")
    finally:
        session_a.close()
        session_b.close()

    winners = [lease for lease in (lease_a, lease_b) if lease is not None]
    assert len(winners) == 1, "both workers claimed the same job"

    with session_factory() as reader:
        job = reader.get(AnalysisJob, job_id)
        assert job.status == "running"
        assert job.worker_id == winners[0].worker_id
        # The loser must not have inflated the attempt budget on its way past.
        assert job.attempt == 1


def test_a_second_claim_of_a_running_job_takes_nothing(session_factory):
    """The swap guard alone, with no candidate-selection help."""

    _, job_id = _bootstrap(session_factory)

    with session_factory() as session:
        assert _plane().claim(session, worker_id="worker-a") is not None

    # worker-b swaps against a candidate that is no longer queued.
    with session_factory() as session:
        assert _PinnedCandidatePlane(job_id, lease_seconds=60).claim(session, worker_id="worker-b") is None

    with session_factory() as reader:
        job = reader.get(AnalysisJob, job_id)
        assert job.worker_id == "worker-a"
        assert job.attempt == 1


def test_two_workers_claim_two_separate_jobs(session_factory):
    with session_factory() as session:
        owner = _owner(session)
        first = _queued_job(session, _repository(session, owner))
        second = _queued_job(session, _repository(session, owner))
        job_ids = {first.id, second.id}

    with session_factory() as session:
        lease_a = _plane().claim(session, worker_id="worker-a")
    with session_factory() as session:
        lease_b = _plane().claim(session, worker_id="worker-b")

    assert lease_a is not None and lease_b is not None
    assert {lease_a.job_id, lease_b.job_id} == job_ids


def test_an_expired_lease_is_reclaimable_by_another_worker(session_factory):
    _, job_id = _bootstrap(session_factory)
    expired_clock = datetime.now(UTC) - timedelta(hours=1)
    stale = _plane(clock=lambda: expired_clock)

    with session_factory() as session:
        assert stale.claim(session, worker_id="worker-a") is not None

    fresh = _plane()
    with session_factory() as session:
        assert fresh.expired_job_ids(session) == (job_id,)
        job = session.get(AnalysisJob, job_id)
        reclaimed = fresh.reclaim(session, job, worker_id="worker-b")
        session.commit()

    assert reclaimed is not None
    assert reclaimed.worker_id == "worker-b"

    with session_factory() as reader:
        row = reader.get(AnalysisJob, job_id)
        assert row.worker_id == "worker-b"
        assert row.status == "running"
        # Reclaim transfers ownership only; the attempt budget is retry policy
        # and must not be spent by a handoff.
        assert row.attempt == 1


def test_an_active_lease_is_never_stolen(session_factory):
    _, job_id = _bootstrap(session_factory)
    plane = _plane(lease_seconds=3600)

    with session_factory() as session:
        assert plane.claim(session, worker_id="worker-a") is not None

    with session_factory() as session:
        assert plane.expired_job_ids(session) == ()
        job = session.get(AnalysisJob, job_id)
        assert plane.reclaim(session, job, worker_id="worker-b") is None

    with session_factory() as reader:
        assert reader.get(AnalysisJob, job_id).worker_id == "worker-a"


def test_a_renewal_between_scan_and_reclaim_defeats_the_reclaim(session_factory):
    """The reclaim guard pins the exact lease instant it observed.

    A sweeper that read an expired row must not act on that stale read if the
    owner renewed in between -- otherwise a live worker loses its job to a
    sweep it had already outrun.
    """

    _, job_id = _bootstrap(session_factory)
    expired_clock = datetime.now(UTC) - timedelta(hours=1)
    stale = _plane(clock=lambda: expired_clock)

    with session_factory() as session:
        lease = stale.claim(session, worker_id="worker-a")
    assert lease is not None

    sweeper = _plane()
    with session_factory() as scan_session:
        # The sweeper observes the row while the lease is still lapsed.
        assert sweeper.expired_job_ids(scan_session) == (job_id,)
        observed = scan_session.get(AnalysisJob, job_id)
        assert observed.worker_id == "worker-a"

        # The rightful owner renews after that scan, from its own session.
        with session_factory() as owner_session:
            assert _plane().renew(owner_session, lease).held is True

        # The sweeper now acts on what it read. Its guard pins that lease
        # instant, which no longer matches the row, so it takes nothing.
        assert sweeper.reclaim(scan_session, observed, worker_id="worker-b") is None

    with session_factory() as reader:
        assert reader.get(AnalysisJob, job_id).worker_id == "worker-a"


def test_lease_expired_compares_naive_and_aware_timestamps(session_factory):
    """SQLite hands back naive datetimes; PostgreSQL hands back aware ones."""

    aware = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    naive = datetime(2026, 1, 1, 12, 0)

    assert lease_expired(naive, aware + timedelta(seconds=1)) is True
    assert lease_expired(naive, aware - timedelta(seconds=1)) is False
    assert lease_expired(aware, naive + timedelta(seconds=1)) is True
    assert lease_expired(aware, naive - timedelta(seconds=1)) is False


# -- ownership enforcement ---------------------------------------------------


def test_a_non_owner_cannot_mutate_another_workers_job(session_factory):
    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        assert plane.claim(session, worker_id="worker-a") is not None

    with session_factory() as session:
        held = plane.update_owned(
            session,
            job_id=job_id,
            worker_id="worker-b",
            values={"status": "completed", "progress": 100},
        )
        session.rollback()

    assert held is False
    with session_factory() as reader:
        job = reader.get(AnalysisJob, job_id)
        assert job.status == "running"
        assert job.worker_id == "worker-a"
        assert job.progress == 0


def test_a_non_owner_cannot_renew_another_workers_lease(session_factory):
    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        owned = plane.claim(session, worker_id="worker-a")
    assert owned is not None

    impostor = JobLease(job_id=job_id, worker_id="worker-b", expires_at=owned.expires_at, attempt=1)
    with session_factory() as session:
        renewal = plane.renew(session, impostor)

    assert renewal.lost is True
    with session_factory() as reader:
        assert reader.get(AnalysisJob, job_id).worker_id == "worker-a"


def test_a_worker_that_lost_its_lease_is_told_so_on_the_next_renewal(session_factory):
    """The handoff signal: renewal is how a displaced owner finds out."""

    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        lease = plane.claim(session, worker_id="worker-a")
    assert lease is not None

    with session_factory() as session:
        assert plane.renew(session, lease).held is True

    # A reclaim hands the job to worker-b.
    with session_factory() as session:
        job = session.get(AnalysisJob, job_id)
        job.lease_expires_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()
        assert plane.reclaim(session, job, worker_id="worker-b") is not None
        session.commit()

    with session_factory() as session:
        assert plane.renew(session, lease).lost is True


def test_a_terminal_job_cannot_be_renewed_or_mutated(session_factory):
    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        lease = plane.claim(session, worker_id="worker-a")
    assert lease is not None

    with session_factory() as session:
        job = session.get(AnalysisJob, job_id)
        job.status = "completed"
        session.commit()

    with session_factory() as session:
        assert plane.renew(session, lease).lost is True
        assert (
            plane.update_owned(session, job_id=job_id, values={"progress": 50}, worker_id="worker-a") is False
        )
        session.rollback()

    with session_factory() as reader:
        assert reader.get(AnalysisJob, job_id).status == "completed"


# -- AC3: cancellation across the boundary -----------------------------------


def test_a_renewal_reports_a_cancellation_request(session_factory):
    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        lease = plane.claim(session, worker_id="worker-a")
    assert lease is not None

    with session_factory() as session:
        assert plane.renew(session, lease).cancel_requested is False
        assert plane.cancel_requested(session, job_id) is False

    with session_factory() as session:
        session.get(AnalysisJob, job_id).cancel_requested = True
        session.commit()

    with session_factory() as session:
        renewal = plane.renew(session, lease)
        assert renewal.held is True
        assert renewal.cancel_requested is True
        assert plane.cancel_requested(session, job_id) is True


def test_a_cancellation_request_survives_a_reclaim_handoff(session_factory):
    """Cancellation must not be dropped when ownership moves."""

    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        assert plane.claim(session, worker_id="worker-a") is not None

    with session_factory() as session:
        job = session.get(AnalysisJob, job_id)
        job.cancel_requested = True
        job.lease_expires_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()

        reclaimed = plane.reclaim(session, job, worker_id="worker-b")
        session.commit()
    assert reclaimed is not None

    with session_factory() as session:
        assert plane.cancel_requested(session, job_id) is True
        assert plane.renew(session, reclaimed).cancel_requested is True


def test_cancellation_is_not_resurrected_after_a_cancelled_job_is_reclaimed(session_factory):
    """A cancelled job is terminal: no later reclaim can put it back to work."""

    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        assert plane.claim(session, worker_id="worker-a") is not None

    with session_factory() as session:
        job = session.get(AnalysisJob, job_id)
        job.status = "cancelled"
        job.worker_id = None
        job.cancel_requested = False
        job.lease_expires_at = None
        job.completed_at = datetime.now(UTC)
        session.commit()

    with session_factory() as session:
        # It is neither claimable nor sweepable, so no worker can own it again.
        assert plane.claim(session, worker_id="worker-b") is None
        assert plane.expired_job_ids(session) == ()

    with session_factory() as reader:
        assert reader.get(AnalysisJob, job_id).status == "cancelled"


def test_the_cancel_not_requested_guard_refuses_to_complete_a_cancelling_job(session_factory):
    """``require_cancel_not_requested`` is what makes cancellation idempotent.

    A completion that raced an accepted cancellation must lose, so the request
    cannot be silently discarded by a worker finishing a moment later.
    """

    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        assert plane.claim(session, worker_id="worker-a") is not None

    with session_factory() as session:
        session.get(AnalysisJob, job_id).cancel_requested = True
        session.commit()

    with session_factory() as session:
        guarded = plane.update_owned(
            session,
            job_id=job_id,
            worker_id="worker-a",
            values={"status": "completed"},
            require_cancel_not_requested=True,
        )
        session.rollback()
        # The same worker may still act on the job -- it only may not pretend
        # the cancellation never happened.
        unguarded = plane.update_owned(
            session,
            job_id=job_id,
            worker_id="worker-a",
            values={"status": "cancelled", "cancel_requested": False},
        )
        session.commit()

    assert guarded is False
    assert unguarded is True
    with session_factory() as reader:
        job = reader.get(AnalysisJob, job_id)
        assert job.status == "cancelled"
        assert job.cancel_requested is False


def test_repeated_cancellation_reads_are_idempotent(session_factory):
    _, job_id = _bootstrap(session_factory)
    plane = _plane()

    with session_factory() as session:
        lease = plane.claim(session, worker_id="worker-a")
        session.get(AnalysisJob, job_id).cancel_requested = True
        session.commit()
    assert lease is not None

    with session_factory() as session:
        for _ in range(3):
            assert plane.cancel_requested(session, job_id) is True
            assert plane.renew(session, lease).cancel_requested is True

    with session_factory() as reader:
        job = reader.get(AnalysisJob, job_id)
        assert job.cancel_requested is True
        assert job.status == "running"


# -- the in-process compatibility runner -------------------------------------


class _RecordingWorker:
    """A worker stand-in that records how the runner drives it."""

    def __init__(self, outcomes: list[bool]) -> None:
        self.worker_id = "worker-recording"
        self._outcomes = list(outcomes)
        self.run_once_calls = 0
        self.sweep_calls = 0
        self.shutdown_calls = 0
        self.drained = threading.Event()

    def run_once(self) -> bool:
        self.run_once_calls += 1
        if self._outcomes:
            return self._outcomes.pop(0)
        self.drained.set()
        return False

    def sweep_stale(self) -> int:
        self.sweep_calls += 1
        return 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def _runner(worker, **kwargs) -> AnalysisWorkerRunner:
    kwargs.setdefault("poll_interval_seconds", 0.01)
    return AnalysisWorkerRunner(worker, **kwargs)


def test_the_runner_sweeps_once_before_it_starts_polling(session_factory):
    worker = _RecordingWorker([])
    runner = _runner(worker)

    runner.sweep_on_start()

    assert worker.sweep_calls == 1
    assert worker.run_once_calls == 0


def test_the_runner_drains_a_backlog_without_sleeping_between_jobs():
    worker = _RecordingWorker([True, True, True])
    runner = _runner(worker, poll_interval_seconds=30)

    runner.start()
    try:
        assert worker.drained.wait(timeout=5), "the runner did not drain the backlog"
    finally:
        runner.stop(timeout=5)

    # Three claimed jobs, then the empty poll that set ``drained``. A runner
    # that slept between jobs could not have reached the fourth call with a
    # 30-second poll interval.
    assert worker.run_once_calls >= 4


def test_the_runner_sweeps_stale_jobs_on_its_configured_cadence():
    worker = _RecordingWorker([])
    runner = _runner(worker, stale_sweep_interval_polls=2)

    runner.start()
    try:
        assert worker.drained.wait(timeout=5)
        _wait_until(lambda: worker.sweep_calls >= 2, timeout=5)
    finally:
        runner.stop(timeout=5)

    # One startup sweep plus at least one periodic sweep from the loop.
    assert worker.sweep_calls >= 2


def test_a_failing_iteration_does_not_kill_the_runner_loop():
    class _ExplodingWorker(_RecordingWorker):
        def run_once(self) -> bool:
            self.run_once_calls += 1
            if self.run_once_calls == 1:
                raise RuntimeError("boom")
            self.drained.set()
            return False

    worker = _ExplodingWorker([])
    runner = _runner(worker)

    runner.start()
    try:
        assert worker.drained.wait(timeout=5), "the loop died on the first failure"
    finally:
        runner.stop(timeout=5)


def test_stopping_the_runner_signals_the_worker_and_joins_the_thread():
    worker = _RecordingWorker([])
    runner = _runner(worker)

    runner.start()
    assert worker.drained.wait(timeout=5)
    runner.stop(timeout=5)

    assert worker.shutdown_calls == 1
    assert runner._thread is None
    assert not any(thread.name == "analysis-worker" for thread in threading.enumerate())


def test_stopping_a_runner_that_never_started_is_safe():
    worker = _RecordingWorker([])
    runner = _runner(worker)

    runner.stop(timeout=1)

    assert worker.shutdown_calls == 1
    assert worker.run_once_calls == 0


def test_starting_a_running_runner_twice_is_refused():
    worker = _RecordingWorker([])
    runner = _runner(worker)

    runner.start()
    try:
        with pytest.raises(RuntimeError):
            runner.start()
    finally:
        runner.stop(timeout=5)


def test_worker_ids_are_unique_within_one_process():
    """Every ownership guard is ``worker_id`` equality, so collisions are fatal."""

    ids = {new_worker_id(pid=7) for _ in range(50)}

    assert len(ids) == 50
    assert all(worker_id.startswith("analysis-worker-7-") for worker_id in ids)
    assert all(len(worker_id) <= 64 for worker_id in ids)


# -- the worker still reaches the queue only through the boundary ------------


def test_the_worker_claims_through_its_injected_control_plane(session_factory):
    """The seam is real: swapping the control plane changes what the worker gets."""

    from app.workers.analysis_worker import AnalysisWorker

    _bootstrap(session_factory)

    class _EmptyQueue(DatabaseAnalysisControlPlane):
        def claim(self, session, *, worker_id):
            return None

    worker = AnalysisWorker(
        session_factory,
        worker_id="worker-a",
        lease_seconds=60,
        control_plane=_EmptyQueue(lease_seconds=60),
    )

    assert worker.run_once() is False

    with session_factory() as reader:
        assert reader.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.status == "queued")) == 1


def test_the_worker_defaults_to_the_database_control_plane(session_factory):
    from app.workers.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(session_factory, worker_id="worker-a", lease_seconds=60)

    assert isinstance(worker.control_plane, DatabaseAnalysisControlPlane)
    assert worker.control_plane.lease_seconds == 60


# -- PostgreSQL: the deployment authority ------------------------------------


def _assert_threaded_claim_race_has_one_winner(factory) -> None:
    """Two real concurrent claims, released together by a barrier."""

    _, job_id = _bootstrap(factory)
    barrier = threading.Barrier(2)
    results: dict[str, object] = {}
    errors: list[BaseException] = []

    def claim(worker_id: str) -> None:
        session = factory()
        try:
            # Both workers resolve their candidate before either writes, then
            # the barrier releases them into the real race window still holding
            # it -- so both genuinely reach the compare-and-swap.
            candidate = _plane().next_eligible_job_id(session)
            assert candidate == job_id
            plane = _PinnedCandidatePlane(candidate, lease_seconds=60)
            barrier.wait(timeout=10)
            results[worker_id] = plane.claim(session, worker_id=worker_id)
        except BaseException as exc:  # noqa: BLE001 - surfaced to the assertion
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=claim, args=(f"worker-{name}",)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert not errors, errors
    assert all(not thread.is_alive() for thread in threads)
    winners = [worker_id for worker_id, lease in results.items() if lease is not None]
    assert len(winners) == 1, f"expected exactly one winner, got {winners}"

    with factory() as reader:
        job = reader.get(AnalysisJob, job_id)
        assert job.status == "running"
        assert job.worker_id == winners[0]
        assert job.attempt == 1


@pytest.mark.skipif(not PG_URL, reason="set PARTHA_TEST_PG_URL to run the Postgres control-plane concurrency test")
def test_concurrent_claims_have_exactly_one_winner_on_postgres():
    """PostgreSQL is the deployment authority for this race.

    SQLite serialises writers, so its version of this race is expressed as an
    explicit interleaving above. Only a real MVCC server exercises two claims
    genuinely in flight at once.
    """

    engine = create_engine(PG_URL)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        _assert_threaded_claim_race_has_one_winner(factory)
    finally:
        engine.dispose()


def _wait_until(predicate, *, timeout: float) -> None:
    """Poll ``predicate`` until true, failing the test if it never becomes true."""

    deadline = datetime.now(UTC) + timedelta(seconds=timeout)
    while datetime.now(UTC) < deadline:
        if predicate():
            return
        threading.Event().wait(0.01)
    raise AssertionError("condition was never met")
