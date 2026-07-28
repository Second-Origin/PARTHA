"""Durable analysis-job execution (#93).

``AnalysisWorker`` claims one queued ``analysis_jobs`` row at a time and runs the
full analysis off the request path through the evidence-backed extraction
pipeline that seals the repository's authoritative ``ri.v1`` snapshot.

``run_once`` is the primary unit both the background loop in ``app.main`` and the
test-suite drive; it is synchronous and deterministic. It claims at most one job
with a portable compare-and-swap (no ``SELECT ... FOR UPDATE SKIP LOCKED``), runs
the stages with cooperative cancellation checks within and between them, and applies a
bounded exponential backoff on failure before finally marking the job ``failed``.

Transactional note (deliberate design, not a gap to "fix"): ``SnapshotStore.seal``
owns its own commit boundary (``snapshot_store.py`` ``_commit_transition``) and
there is no way to merge that commit with the job row's ``status='completed'``
commit without modifying the sealed #88 store (out of scope). Sealing and
job-completion are therefore two separate commits, not one atomic transaction.
This is made safe by *idempotent reconciliation*, not single-phase atomicity: if
the process dies between the two commits, the job is left ``running`` with a
lease that will expire, and the stale-job sweep (Task 4) reconciles by checking
``SnapshotStore.find_completed_for_owner`` for a matching identity — finding the
already-sealed snapshot, it marks the job ``completed`` pointing at it rather
than redoing the work. Do not collapse these two commits into one.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.analysis.resource_budget import (
    DEFAULT_MAX_ANALYSIS_SECONDS,
    DEFAULT_MAX_PROCESS_RSS_BYTES,
    DEFAULT_MAX_REPOSITORY_SOURCE_BYTES,
    RESOURCE_EXCEEDED_CODE,
    AnalysisResourceBudget,
    AnalysisResourceExceeded,
)
from app.analysis.source_stream import RepositorySourceStream
from app.extraction.base import ExtractedEvidence
from app.extraction.dependencies import (
    DEPENDENCY_SET_ARRAY_KEYS,
    merge_dependency_facts,
)
from app.extraction import production_extractors
from app.extraction.pipeline import (
    DEFAULT_MAX_SOURCE_BYTES,
    ExtractionPipeline,
    ProducedExtraction,
)
from app.intelligence.classification import RoleClassifier
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models.analysis_job import AnalysisJob
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiSnapshot
from app.services.analysis_job_service import (
    ANALYSIS_CONFIG_HASH,
    ANALYSIS_PRODUCER_VERSION_SET,
    ANALYSIS_SCHEMA_VERSION,
)

_MAX_ERROR_MESSAGE = 1024
_ERROR_CODE = "RI-JOB-FAILED"
_CANCELLED_CODE = "RI-JOB-CANCELLED"
_STALE_CODE = "RI-JOB-STALE"
_STALE_MESSAGE = "Analysis worker lease expired before the job completed."

logger = logging.getLogger(__name__)


class _LeaseLostError(RuntimeError):
    """Internal control flow for a job reclaimed by another worker."""


class _CancellationObserved(RuntimeError):
    """Internal control flow for cancellation observed by a heartbeat."""


@dataclass
class _HeartbeatState:
    """Thread-safe signals returned by one stage heartbeat."""

    stop: threading.Event = field(default_factory=threading.Event)
    ownership_lost: threading.Event = field(default_factory=threading.Event)
    cancel_requested: threading.Event = field(default_factory=threading.Event)
    failure: Exception | None = None
    thread: threading.Thread | None = None


@dataclass
class _StageContext:
    """Mutable state threaded through one job's stage pipeline."""

    session: Session
    job: AnalysisJob
    record: RepositoryRecord | None
    store: SnapshotStore | None = None
    snapshot: RiSnapshot | None = None
    reused: bool = False
    resource_budget: AnalysisResourceBudget | None = None
    heartbeat: _HeartbeatState | None = None


class AnalysisWorker:
    """Claim and execute one durable analysis job at a time."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        worker_id: str,
        lease_seconds: int,
        max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
        max_repository_source_bytes: int = DEFAULT_MAX_REPOSITORY_SOURCE_BYTES,
        max_process_rss_bytes: int = DEFAULT_MAX_PROCESS_RSS_BYTES,
        max_analysis_seconds: float = DEFAULT_MAX_ANALYSIS_SECONDS,
        rss_reader: Callable[[], int] | None = None,
        monotonic: Callable[[], float] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.max_source_bytes = max_source_bytes
        self.max_repository_source_bytes = max_repository_source_bytes
        self.max_process_rss_bytes = max_process_rss_bytes
        self.max_analysis_seconds = max_analysis_seconds
        self._rss_reader = rss_reader
        self._monotonic = monotonic
        self._clock = clock
        self._heartbeat_interval_seconds = heartbeat_interval_seconds or min(max(lease_seconds / 3, 0.1), 5.0)
        self._shutdown = threading.Event()

    # -- public API ----------------------------------------------------------

    def run_once(self) -> bool:
        """Claim and fully execute at most one queued job.

        Returns ``True`` if a job was claimed (regardless of its outcome),
        ``False`` if the queue was empty. Synchronous and deterministic.
        """

        session = self.session_factory()
        try:
            job = self._claim(session)
            if job is None:
                return False
            # Draining the stage generator runs the whole job to a terminal
            # state; tests can instead step the generator to interleave a cancel.
            for _ in self._execute_stages(session, job):
                pass
            return True
        finally:
            session.close()

    def shutdown(self) -> None:
        """Stop stage heartbeat loops during application shutdown."""

        self._shutdown.set()

    def sweep_stale(self) -> int:
        """Reconcile running jobs whose worker lease has expired.

        A completed snapshot means the old worker died after the snapshot seal
        commit but before the job-completion commit, so the job is healed to
        ``completed`` without repeating analysis. Otherwise any orphaned
        building snapshot is failed and the job is either requeued with bounded
        backoff or terminally failed when its attempt budget is exhausted.
        """

        session = self.session_factory()
        try:
            now = self._clock()
            stale_ids = tuple(
                session.scalars(
                    select(AnalysisJob.id)
                    .where(
                        AnalysisJob.status == "running",
                        AnalysisJob.lease_expires_at.is_not(None),
                        AnalysisJob.lease_expires_at < now,
                    )
                    .order_by(AnalysisJob.lease_expires_at, AnalysisJob.created_at)
                )
            )
            reclaimed = 0
            for job_id in stale_ids:
                # Re-read each row so another sweeper that already reconciled it
                # turns this pass into a harmless no-op.
                session.expire_all()
                job = session.get(AnalysisJob, job_id)
                if (
                    job is None
                    or job.status != "running"
                    or job.lease_expires_at is None
                    or not self._lease_expired(job.lease_expires_at, now)
                ):
                    continue
                if self._reconcile_stale(session, job, now):
                    reclaimed += 1
            return reclaimed
        finally:
            session.close()

    # -- claim ---------------------------------------------------------------

    def _claim(self, session: Session) -> AnalysisJob | None:
        """Atomically claim the oldest eligible queued job, or return None.

        The claim is a portable compare-and-swap rather than
        ``SELECT ... FOR UPDATE SKIP LOCKED``: pick the oldest eligible id, then
        ``UPDATE ... WHERE id = :id AND status='queued'``. The ``status='queued'``
        predicate is the atomic guard — two workers racing for the same row see
        exactly one non-zero ``rowcount``; the loser gets ``None`` and retries.
        """

        now = self._clock()
        candidate_id = session.scalar(
            select(AnalysisJob.id)
            .where(
                AnalysisJob.status == "queued",
                or_(AnalysisJob.next_attempt_at.is_(None), AnalysisJob.next_attempt_at <= now),
            )
            .order_by(AnalysisJob.created_at)
            .limit(1)
        )
        if candidate_id is None:
            return None
        result = session.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == candidate_id, AnalysisJob.status == "queued")
            .values(
                status="running",
                worker_id=self.worker_id,
                lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                started_at=func.coalesce(AnalysisJob.started_at, now),
                attempt=AnalysisJob.attempt + 1,
                next_attempt_at=None,
                updated_at=now,
            )
        )
        session.commit()
        if result.rowcount == 0:
            # Another worker won the compare-and-swap for this row.
            return None
        return session.get(AnalysisJob, candidate_id)

    # -- stage pipeline ------------------------------------------------------

    def _execute_stages(self, session: Session, job: AnalysisJob) -> Iterator[_StageContext]:
        """Run the job's stages, yielding at each boundary.

        Yielding after every stage gives the background loop a plain drain and
        gives tests a seam to set ``cancel_requested`` between two stages. The
        cancel flag is re-read from the row before each stage so a concurrent
        ``AnalysisJobService.cancel`` is observed cooperatively.
        """

        ctx = _StageContext(
            session=session,
            job=job,
            record=session.get(RepositoryRecord, job.repository_id),
        )
        stages = (
            ("extracting-modules", 35, self._stage_open_snapshot),
            ("building-dependency-graph", 75, self._stage_extract),
            ("preparing-architecture", 90, self._stage_seal),
        )
        try:
            for stage_name, progress, stage in stages:
                if self._cancel_requested(ctx):
                    self._cancel(ctx)
                    yield ctx
                    return
                with self._heartbeat(ctx):
                    self._check_heartbeat(ctx)
                    stage(ctx)
                    self._check_heartbeat(ctx)
                self._checkpoint(ctx, stage_name, progress)
                yield ctx
            if self._cancel_requested(ctx):
                self._cancel(ctx)
                yield ctx
                return
            self._complete(ctx)
            yield ctx
        except _CancellationObserved:
            session.rollback()
            current = session.get(AnalysisJob, job.id)
            if current is None:
                self._log_lease_lost(job.id)
                return
            ctx.job = current
            ctx.record = session.get(RepositoryRecord, current.repository_id)
            try:
                self._cancel(ctx)
            except _LeaseLostError:
                self._log_lease_lost(job.id)
                return
            yield ctx
            return
        except _LeaseLostError:
            session.rollback()
            self._log_lease_lost(job.id)
            return
        except AnalysisResourceExceeded as exc:
            try:
                self._fail_resource_exceeded(ctx, exc)
            except _LeaseLostError:
                self._log_lease_lost(job.id)
                return
            yield ctx
            return
        except Exception as exc:  # noqa: BLE001 - bounded retry is the contract
            try:
                self._retry_or_fail(ctx, exc)
            except _LeaseLostError:
                self._log_lease_lost(job.id)
                return
            yield ctx

    def _stage_open_snapshot(self, ctx: _StageContext) -> None:
        """Open (or reuse) the snapshot for this job's exact semantic identity.

        Submit and execution must key on the identical identity constants or the
        idempotency guarantee breaks, so the shared ``ANALYSIS_*`` constants are
        used here. ``job.snapshot_id`` is recorded as soon as the id exists —
        before any facts or sealing — so a later crash-recovery sweep can find and
        fail an orphaned ``building`` snapshot.
        """

        record = self._require_record(ctx)
        record.status = "analysing"
        record.analysis_stage = "extracting-modules"
        record.analysis_progress = 35
        revision = self._require_revision(record)
        ctx.store = SnapshotStore(ctx.session)
        snapshot, reused = ctx.store.get_or_reuse(
            repository_id=record.id,
            revision=revision,
            producer_version_set=ANALYSIS_PRODUCER_VERSION_SET,
            schema_version=ANALYSIS_SCHEMA_VERSION,
            config_hash=ANALYSIS_CONFIG_HASH,
        )
        ctx.snapshot = snapshot
        ctx.reused = reused
        ctx.job.snapshot_id = snapshot.snapshot_id
        if not reused:
            ctx.resource_budget = self._new_resource_budget()

    def _stage_extract(self, ctx: _StageContext) -> None:
        """Run the evidence pipeline and persist every extracted fact.

        A reused (already-sealed) snapshot needs no work: extraction and
        resolution are skipped and sealing becomes a no-op.
        """

        if ctx.reused:
            return
        record = self._require_record(ctx)
        store = ctx.store
        snapshot = ctx.snapshot
        assert store is not None and snapshot is not None
        budget = ctx.resource_budget
        assert budget is not None
        sources = RepositorySourceStream(
            root=Path(record.local_path),
            file_tree=record.file_tree or (),
            max_file_bytes=self.max_source_bytes,
            budget=budget,
            check_cancelled=lambda: self._check_heartbeat(ctx),
        )
        pipeline = ExtractionPipeline(
            production_extractors(),
            max_source_bytes=self.max_source_bytes,
        )
        deferred_dependencies: list[ProducedExtraction] = []
        for produced in pipeline.iter_run(
            sources,
            check_cancelled=lambda: self._check_heartbeat(ctx),
        ):
            if any(node.node_kind == "dependency" for node in produced.result.nodes):
                # Dependency observations reference these nodes, so the complete
                # manifest and lockfile results must wait for the cross-file
                # reducer that folds them onto one identity.
                deferred_dependencies.append(produced)
                continue
            self._persist_produced(store, snapshot, produced, ctx)
        for produced in self._merge_dependency_declarations(tuple(deferred_dependencies)):
            self._persist_produced(store, snapshot, produced, ctx)
        self._check_heartbeat(ctx)
        RelationshipResolver(store).resolve(
            snapshot,
            check_cancelled=lambda: self._check_heartbeat(ctx),
        )
        self._check_heartbeat(ctx)
        RoleClassifier(store).classify(
            snapshot,
            check_cancelled=lambda: self._check_heartbeat(ctx),
        )
        self._check_heartbeat(ctx)

    def _stage_seal(self, ctx: _StageContext) -> None:
        """Seal the building snapshot (commits internally, see the module note)."""

        if ctx.reused:
            return
        assert ctx.store is not None and ctx.snapshot is not None
        self._check_heartbeat(ctx)
        # ``seal`` commits internally, so acquire the guarded job row in the
        # same transaction before allowing the snapshot transition to commit.
        self._lock_owned_job(ctx, require_cancel_not_requested=True)
        ctx.store.seal(
            ctx.snapshot,
            check_cancelled=lambda: self._check_heartbeat(ctx),
        )

    # -- terminal transitions ------------------------------------------------

    def _complete(self, ctx: _StageContext) -> None:
        """Mark the job (and its repository record) completed.

        This commit is deliberately separate from ``seal``'s commit (see the
        module note); do not merge them.
        """

        now = self._clock()
        job_id = ctx.job.id
        try:
            self._update_owned_job(
                ctx,
                require_cancel_not_requested=True,
                status="completed",
                stage="completed",
                progress=100,
                cancel_requested=False,
                worker_id=None,
                lease_expires_at=None,
                error_code=None,
                error_message=None,
                completed_at=now,
                updated_at=now,
            )
        except _LeaseLostError:
            # Cancellation can be accepted after the final cooperative read but
            # before this completion CAS. If this worker still owns that running
            # row, honour the accepted request instead of abandoning/completing.
            job = ctx.session.get(AnalysisJob, job_id)
            if job is not None and job.status == "running" and job.worker_id == self.worker_id and job.cancel_requested:
                ctx.job = job
                ctx.record = ctx.session.get(RepositoryRecord, job.repository_id)
                self._cancel(ctx)
                return
            raise
        if ctx.record is not None:
            ctx.record.status = "completed"
            ctx.record.analysis_stage = "completed"
            ctx.record.analysis_progress = 100
            ctx.record.error_message = None
            ctx.record.analysed_at = now
        ctx.session.commit()

    def _cancel(self, ctx: _StageContext) -> None:
        """Honour a cooperative cancel: fail any open snapshot, cancel the job."""

        self._lock_owned_job(ctx)
        snapshot = ctx.session.get(RiSnapshot, ctx.job.snapshot_id) if ctx.job.snapshot_id is not None else None
        if snapshot is not None and snapshot.state == "completed":
            self._complete_sealed_snapshot(ctx, snapshot)
            return
        self._fail_open_snapshot(ctx, code=_CANCELLED_CODE)
        now = self._clock()
        self._update_owned_job(
            ctx,
            status="cancelled",
            worker_id=None,
            lease_expires_at=None,
            next_attempt_at=None,
            completed_at=now,
            updated_at=now,
        )
        if ctx.record is not None:
            ctx.record.status = "cancelled"
            ctx.record.analysis_stage = None
            ctx.record.analysis_progress = 0
            ctx.record.error_message = None
            ctx.record.analysed_at = None
        ctx.session.commit()

    def _retry_or_fail(self, ctx: _StageContext, exc: Exception) -> None:
        """Bounded retry: re-queue with backoff, or fail after ``max_attempts``."""

        session = ctx.session
        session.rollback()
        # Rollback expired the in-memory rows; reload from the row that the claim
        # already committed so ``attempt``/``max_attempts`` reflect the database.
        job = session.get(AnalysisJob, ctx.job.id)
        if job is None:
            raise _LeaseLostError(ctx.job.id)
        ctx.job = job
        ctx.record = session.get(RepositoryRecord, job.repository_id)
        now = self._clock()
        try:
            self._lock_owned_job(ctx, require_cancel_not_requested=True)
        except _CancellationObserved:
            self._cancel(ctx)
            return
        snapshot = session.get(RiSnapshot, job.snapshot_id) if job.snapshot_id else None
        if snapshot is not None and snapshot.state == "completed":
            self._update_owned_job(
                ctx,
                status="completed",
                stage="completed",
                progress=100,
                cancel_requested=False,
                worker_id=None,
                lease_expires_at=None,
                next_attempt_at=None,
                error_code=None,
                error_message=None,
                completed_at=snapshot.sealed_at or now,
                updated_at=now,
            )
            if ctx.record is not None:
                ctx.record.status = "completed"
                ctx.record.analysis_stage = "completed"
                ctx.record.analysis_progress = 100
                ctx.record.error_message = None
                ctx.record.analysed_at = snapshot.sealed_at or now
            session.commit()
            return
        self._fail_open_snapshot(ctx, code=_ERROR_CODE)
        if job.attempt >= job.max_attempts:
            self._update_owned_job(
                ctx,
                status="failed",
                worker_id=None,
                lease_expires_at=None,
                next_attempt_at=None,
                error_code=_ERROR_CODE,
                error_message=self._error_message(exc),
                completed_at=now,
                updated_at=now,
            )
            if ctx.record is not None:
                ctx.record.status = "error"
                ctx.record.analysis_stage = None
                ctx.record.analysis_progress = 0
                ctx.record.error_message = "Repository analysis failed."
            session.commit()
            return
        self._update_owned_job(
            ctx,
            status="queued",
            worker_id=None,
            lease_expires_at=None,
            next_attempt_at=now + timedelta(seconds=self._backoff(job.attempt)),
            error_code=_ERROR_CODE,
            error_message=self._error_message(exc),
            updated_at=now,
        )
        session.commit()

    def _fail_resource_exceeded(self, ctx: _StageContext, exc: AnalysisResourceExceeded) -> None:
        """Fail a deterministic resource breach terminally instead of retrying it."""

        session = ctx.session
        session.rollback()
        job = session.get(AnalysisJob, ctx.job.id)
        if job is None:
            raise _LeaseLostError(ctx.job.id)
        ctx.job = job
        ctx.record = session.get(RepositoryRecord, job.repository_id)
        now = self._clock()
        try:
            self._lock_owned_job(ctx, require_cancel_not_requested=True)
        except _CancellationObserved:
            self._cancel(ctx)
            return
        snapshot = session.get(RiSnapshot, job.snapshot_id) if job.snapshot_id else None
        if snapshot is not None and snapshot.state == "completed":
            self._complete_sealed_snapshot(ctx, snapshot)
            return
        self._fail_open_snapshot(ctx, code=RESOURCE_EXCEEDED_CODE)
        self._update_owned_job(
            ctx,
            status="failed",
            worker_id=None,
            lease_expires_at=None,
            next_attempt_at=None,
            error_code=RESOURCE_EXCEEDED_CODE,
            error_message=self._error_message(exc),
            completed_at=now,
            updated_at=now,
        )
        if ctx.record is not None:
            ctx.record.status = "error"
            ctx.record.analysis_stage = None
            ctx.record.analysis_progress = 0
            ctx.record.error_message = "Repository analysis exceeded its resource budget."
        session.commit()

    def _reconcile_stale(self, session: Session, job: AnalysisJob, now: datetime) -> bool:
        """Atomically claim and reconcile one expired running job."""

        stale_worker_id = job.worker_id
        stale_lease_expires_at = job.lease_expires_at
        result = session.execute(
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job.id,
                AnalysisJob.status == "running",
                AnalysisJob.worker_id == stale_worker_id,
                AnalysisJob.lease_expires_at == stale_lease_expires_at,
                AnalysisJob.lease_expires_at < now,
            )
            .values(
                worker_id=self.worker_id,
                lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                updated_at=now,
            )
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount == 0:
            session.rollback()
            return False

        record = session.get(RepositoryRecord, job.repository_id)
        snapshot = session.get(RiSnapshot, job.snapshot_id) if job.snapshot_id else None
        ctx = _StageContext(session=session, job=job, record=record)

        if job.cancel_requested:
            self._cancel(ctx)
            return True

        if snapshot is not None and snapshot.state == "completed":
            self._update_owned_job(
                ctx,
                status="completed",
                stage="completed",
                progress=100,
                cancel_requested=False,
                worker_id=None,
                lease_expires_at=None,
                next_attempt_at=None,
                error_code=None,
                error_message=None,
                completed_at=snapshot.sealed_at or now,
                updated_at=now,
            )
            if record is not None:
                record.status = "completed"
                record.analysis_stage = "completed"
                record.analysis_progress = 100
                record.error_message = None
                record.analysed_at = snapshot.sealed_at or now
            session.commit()
            return True

        if snapshot is not None and snapshot.state == "building":
            # mark_failed owns a commit boundary. Do this before changing the job
            # so its transition cannot accidentally commit a half-reconciled row.
            SnapshotStore(session).mark_failed(snapshot, code=_STALE_CODE)

        if job.attempt < job.max_attempts:
            self._update_owned_job(
                ctx,
                status="queued",
                worker_id=None,
                lease_expires_at=None,
                next_attempt_at=now + timedelta(seconds=self._backoff(job.attempt)),
                error_code=_STALE_CODE,
                error_message=_STALE_MESSAGE,
                updated_at=now,
            )
            if record is not None:
                record.status = "analysing"
                record.analysis_stage = None
                record.analysis_progress = 0
                record.error_message = None
        else:
            self._update_owned_job(
                ctx,
                status="failed",
                worker_id=None,
                lease_expires_at=None,
                next_attempt_at=None,
                error_code=_STALE_CODE,
                error_message=_STALE_MESSAGE,
                completed_at=now,
                updated_at=now,
            )
            if record is not None:
                record.status = "error"
                record.analysis_stage = None
                record.analysis_progress = 0
                record.error_message = "Repository analysis failed after its worker lease expired."
        session.commit()
        return True

    # -- helpers -------------------------------------------------------------

    def _checkpoint(self, ctx: _StageContext, stage: str, progress: int) -> None:
        """Persist stage/progress and renew the lease at a stage boundary."""

        now = self._clock()
        self._update_owned_job(
            ctx,
            stage=stage,
            progress=progress,
            lease_expires_at=now + timedelta(seconds=self.lease_seconds),
            updated_at=now,
        )
        ctx.session.commit()

    def _update_owned_job(
        self,
        ctx: _StageContext,
        *,
        require_cancel_not_requested: bool = False,
        **values: object,
    ) -> None:
        """Update a running job only while this worker still owns it."""

        job_id = ctx.job.id
        ownership = [
            AnalysisJob.id == job_id,
            AnalysisJob.worker_id == self.worker_id,
            AnalysisJob.status == "running",
        ]
        if require_cancel_not_requested:
            ownership.append(AnalysisJob.cancel_requested.is_(False))
        with ctx.session.no_autoflush:
            result = ctx.session.execute(
                update(AnalysisJob).where(*ownership).values(**values).execution_options(synchronize_session="fetch")
            )
        if result.rowcount == 0:
            ctx.session.rollback()
            raise _LeaseLostError(job_id)

    def _lock_owned_job(self, ctx: _StageContext, *, require_cancel_not_requested: bool = False) -> None:
        """Lock the running row after atomically confirming this worker owns it."""

        try:
            self._update_owned_job(
                ctx,
                require_cancel_not_requested=require_cancel_not_requested,
                updated_at=AnalysisJob.updated_at,
            )
        except _LeaseLostError:
            if require_cancel_not_requested:
                current = ctx.session.get(AnalysisJob, ctx.job.id)
                if (
                    current is not None
                    and current.status == "running"
                    and current.worker_id == self.worker_id
                    and current.cancel_requested
                ):
                    ctx.job = current
                    raise _CancellationObserved(current.id) from None
            raise

    def _cancel_requested(self, ctx: _StageContext) -> bool:
        return bool(ctx.session.scalar(select(AnalysisJob.cancel_requested).where(AnalysisJob.id == ctx.job.id)))

    def _fail_open_snapshot(self, ctx: _StageContext, *, code: str) -> None:
        """Mark an opened-but-unsealed snapshot ``failed`` (no-op if reused/sealed)."""

        if ctx.reused or ctx.job.snapshot_id is None:
            return
        snapshot = ctx.session.get(RiSnapshot, ctx.job.snapshot_id)
        if snapshot is not None and snapshot.state == "building":
            SnapshotStore(ctx.session).mark_failed(snapshot, code=code)

    def _log_lease_lost(self, job_id: str) -> None:
        logger.warning(
            "Analysis worker lost job ownership; abandoning execution",
            extra={"job_id": job_id, "worker_id": self.worker_id},
        )

    @contextmanager
    def _heartbeat(self, ctx: _StageContext) -> Iterator[_HeartbeatState]:
        """Renew one running job from an independent session during a stage."""

        state = _HeartbeatState()
        self._heartbeat_once(ctx.job.id, state)

        def _run() -> None:
            while not state.stop.wait(self._heartbeat_interval_seconds):
                if self._shutdown.is_set():
                    return
                self._heartbeat_once(ctx.job.id, state)
                if state.ownership_lost.is_set() or state.cancel_requested.is_set() or state.failure:
                    return

        if not state.ownership_lost.is_set() and not state.cancel_requested.is_set() and not state.failure:
            state.thread = threading.Thread(
                target=_run,
                name=f"analysis-heartbeat-{ctx.job.id}",
                daemon=True,
            )
            state.thread.start()
        ctx.heartbeat = state
        try:
            yield state
        finally:
            ctx.heartbeat = None
            state.stop.set()
            if state.thread is not None:
                state.thread.join(timeout=max(self._heartbeat_interval_seconds * 2, 1.0))
                if state.thread.is_alive():
                    logger.warning(
                        "Analysis heartbeat did not stop promptly",
                        extra={"job_id": ctx.job.id, "worker_id": self.worker_id},
                    )

    def _heartbeat_once(self, job_id: str, state: _HeartbeatState) -> None:
        """Atomically renew ownership and return the cancellation flag."""

        session = self.session_factory()
        sqlite_connection = None
        sqlite_busy_timeout = None

        def _restore_sqlite_timeout() -> None:
            nonlocal sqlite_connection
            if sqlite_connection is None or sqlite_busy_timeout is None:
                return
            try:
                cursor = sqlite_connection.cursor()
                cursor.execute(f"PRAGMA busy_timeout = {sqlite_busy_timeout}")
                cursor.close()
            except Exception:  # noqa: BLE001 - discard a modified connection
                session.invalidate()
            finally:
                sqlite_connection = None

        try:
            if session.bind is not None and session.bind.dialect.name == "sqlite":
                connection = session.connection()
                sqlite_connection = connection.connection.driver_connection
                cursor = sqlite_connection.cursor()
                sqlite_busy_timeout = int(cursor.execute("PRAGMA busy_timeout").fetchone()[0])
                # SQLite serializes all writers. If the stage already owns the
                # database write lock, a sweeper cannot reclaim the job either,
                # so the heartbeat must not block stage cleanup behind that lock.
                cursor.execute("PRAGMA busy_timeout = 0")
                cursor.close()
            now = self._clock()
            row = session.execute(
                update(AnalysisJob)
                .where(
                    AnalysisJob.id == job_id,
                    AnalysisJob.status == "running",
                    AnalysisJob.worker_id == self.worker_id,
                )
                .values(
                    lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                    updated_at=now,
                )
                .returning(AnalysisJob.cancel_requested)
                .execution_options(synchronize_session=False)
            ).first()
            if row is None:
                _restore_sqlite_timeout()
                session.rollback()
                state.ownership_lost.set()
                return
            _restore_sqlite_timeout()
            session.commit()
            if row[0]:
                state.cancel_requested.set()
        except Exception as exc:  # noqa: BLE001 - surfaced to the owning worker
            _restore_sqlite_timeout()
            session.rollback()
            # A SQLite writer prevents every other SQLite writer, including a
            # stale sweeper. Skipping that transient pulse avoids a false retry;
            # PostgreSQL heartbeats remain fully independent and guarded.
            if session.bind is not None and session.bind.dialect.name == "sqlite" and "locked" in str(exc).lower():
                logger.debug("SQLite analysis heartbeat skipped while the stage held the write lock")
            else:
                state.failure = exc
        finally:
            _restore_sqlite_timeout()
            session.close()

    @staticmethod
    def _check_heartbeat(ctx: _StageContext) -> None:
        state = ctx.heartbeat
        if state is not None:
            if state.ownership_lost.is_set():
                raise _LeaseLostError(ctx.job.id)
            if state.cancel_requested.is_set():
                raise _CancellationObserved(ctx.job.id)
            if state.failure is not None:
                raise state.failure
        if ctx.resource_budget is not None:
            ctx.resource_budget.check()

    def _new_resource_budget(self) -> AnalysisResourceBudget:
        kwargs: dict[str, object] = {
            "max_source_bytes": self.max_repository_source_bytes,
            "max_rss_bytes": self.max_process_rss_bytes,
            "max_seconds": self.max_analysis_seconds,
        }
        if self._rss_reader is not None:
            kwargs["rss_reader"] = self._rss_reader
        if self._monotonic is not None:
            kwargs["monotonic"] = self._monotonic
        return AnalysisResourceBudget(**kwargs)  # type: ignore[arg-type]

    def _complete_sealed_snapshot(self, ctx: _StageContext, snapshot: RiSnapshot) -> None:
        """Make an already-sealed snapshot authoritative over cancellation."""

        now = self._clock()
        completed_at = snapshot.sealed_at or now
        self._update_owned_job(
            ctx,
            status="completed",
            stage="completed",
            progress=100,
            cancel_requested=False,
            worker_id=None,
            lease_expires_at=None,
            next_attempt_at=None,
            error_code=None,
            error_message=None,
            completed_at=completed_at,
            updated_at=now,
        )
        if ctx.record is not None:
            ctx.record.status = "completed"
            ctx.record.analysis_stage = "completed"
            ctx.record.analysis_progress = 100
            ctx.record.error_message = None
            ctx.record.analysed_at = completed_at
        ctx.session.commit()

    @staticmethod
    def _merge_dependency_declarations(
        produced: tuple[ProducedExtraction, ...],
    ) -> tuple[ProducedExtraction, ...]:
        """Fold per-file dependency facts onto one node before persistence.

        Scoped to this worker's single repository-wide extraction stream, where
        every manifest and lockfile in the repository has been seen;
        ``ExtractionPipeline`` itself is unchanged. The reducer lives in
        :mod:`app.extraction.dependencies` so the golden benchmark seals the
        identical merged shape this worker persists.
        """

        return merge_dependency_facts(produced)

    def _persist_produced(
        self,
        store: SnapshotStore,
        snapshot: RiSnapshot,
        produced: ProducedExtraction,
        ctx: _StageContext | None = None,
    ) -> None:
        """Convert one ``ExtractionResult`` into snapshot writes.

        This mirrors the proven benchmark adapter conversion, but writes to the
        production ``SnapshotStore`` instead of building comparison facts. Evidence
        provenance carries the emitting producer, which is a declared member of the
        analysis producer set, so sealing's ``declared ⊇ observed`` check holds.
        """

        result = produced.result
        for node in result.nodes:
            if ctx is not None:
                self._check_heartbeat(ctx)
            set_array_keys = frozenset(
                key
                for key in ("decorators", *sorted(DEPENDENCY_SET_ARRAY_KEYS))
                if node.properties and key in node.properties
            )
            store.add_node(
                snapshot,
                node_kind=node.node_kind,
                stable_key=node.stable_key,
                name=node.name,
                language=node.language,
                properties=node.properties,
                set_array_keys=set_array_keys,
                evidence=[self._evidence(item, produced) for item in node.evidence],
            )
        for observation in result.observations:
            if ctx is not None:
                self._check_heartbeat(ctx)
            store.add_observation(
                snapshot,
                observed_kind=observation.observed_kind,
                subject_kind=observation.subject_kind,
                subject_key=observation.subject_key,
                referent_text=observation.referent_text,
                ordinal=observation.ordinal,
                evidence=self._evidence(observation.evidence, produced),
            )
        for diagnostic in result.diagnostics:
            if ctx is not None:
                self._check_heartbeat(ctx)
            store.add_diagnostic(
                snapshot,
                code=diagnostic.code,
                category=diagnostic.category,
                severity=diagnostic.severity,
                message=diagnostic.message,
                producer=produced.producer,
                path=diagnostic.path,
                span=diagnostic.span,
                subject=diagnostic.subject,
                details=diagnostic.details,
            )

    @staticmethod
    def _evidence(item: ExtractedEvidence, produced: ProducedExtraction) -> Evidence:
        return Evidence(
            path=item.path,
            start_line=item.start_line,
            end_line=item.end_line,
            extractor=produced.producer_name,
            extractor_version=produced.producer_version,
            logical_line_count=item.logical_line_count,
            granularity=item.granularity,
        )

    @staticmethod
    def _require_record(ctx: _StageContext) -> RepositoryRecord:
        if ctx.record is None:
            raise RuntimeError("analysis job references a repository that no longer exists")
        return ctx.record

    @staticmethod
    def _require_revision(record: RepositoryRecord) -> Revision:
        if record.revision_kind is None or record.revision_value is None:
            raise RuntimeError("repository has no analyzable revision")
        return Revision(record.revision_kind, record.revision_value, record.revision_ref)

    @staticmethod
    def _backoff(attempt: int) -> int:
        """Bounded exponential backoff in seconds (capped at 60)."""

        return min(2**attempt, 60)

    @staticmethod
    def _lease_expired(lease_expires_at: datetime, now: datetime) -> bool:
        """Compare SQLite-naive and timezone-aware persisted timestamps safely."""

        if lease_expires_at.tzinfo is None and now.tzinfo is not None:
            lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
        elif lease_expires_at.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return lease_expires_at < now

    @staticmethod
    def _error_message(exc: Exception) -> str:
        message = str(exc) or exc.__class__.__name__
        return message[:_MAX_ERROR_MESSAGE]
