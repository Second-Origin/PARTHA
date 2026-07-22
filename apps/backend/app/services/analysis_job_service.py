"""Durable analysis-job lifecycle: submit, status, and cancel (#93).

This service owns the *durable* side of analysis: it turns a
``POST /analysis/{repository_id}/start`` request into an ``analysis_jobs`` row
(fast, off the request path) and answers status/cancel queries against that
row. The heavy work — legacy intelligence plus the evidence-backed extraction
pipeline that seals a Repository Intelligence snapshot — runs in
``app.workers.analysis_worker.AnalysisWorker``, never inside the request.

A job's semantic identity is ``(repository_id, revision_value, config_hash)``,
mirroring ``SnapshotStore``'s own semantic-identity concept
(RFC-0001 §3.3). ``config_hash`` is a stable content hash of the analysis
configuration; there is no tunable analysis configuration today, so it hashes a
fixed empty-config sentinel via the same helper ``SnapshotStore`` uses. The
field exists so that a future config change naturally produces a new identity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictServiceError, NotFoundError, ServiceError
from app.extraction.pipeline import ExtractionPipeline
from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence import canonical
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import SnapshotStore
from app.models.analysis_job import AnalysisJob
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiSnapshot
from app.repositories.repository_repository import RepositoryRepository


def _analysis_producer_version_set() -> tuple[str, ...]:
    """The fixed, planned producer set the analysis pipeline declares.

    The semantic identity (RFC §3.3) must fix the *planned* producer set before
    any facts are written, so both ``submit`` (looking for a reusable snapshot)
    and the worker (opening/sealing one) key on the identical set. Deriving it
    from the collaborator classes keeps it in lockstep with the pipeline the
    worker actually runs. Declaring a producer that emits nothing for a given
    repository is safe: sealing requires declared ⊇ observed, never equality.
    """

    return tuple(
        sorted(
            {
                f"{ExtractionPipeline.inventory_name}@{ExtractionPipeline.inventory_version}",
                f"{PythonExtractor.name}@{PythonExtractor.version}",
                f"{TypeScriptExtractor.name}@{TypeScriptExtractor.version}",
                f"{RelationshipResolver.name}@{RelationshipResolver.version}",
            }
        )
    )


# Shared identity constants — imported by the worker so submit and execution
# agree on the exact semantic identity.
ANALYSIS_PRODUCER_VERSION_SET = _analysis_producer_version_set()
ANALYSIS_CONFIG_HASH = canonical.compute_config_hash(None)
ANALYSIS_SCHEMA_VERSION = canonical.SCHEMA_VERSION


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AnalysisJobService:
    """Owner-scoped durable analysis-job submission, status, and cancellation."""

    def __init__(self, db: Session, owner_id: str) -> None:
        self.db = db
        self.owner_id = owner_id
        self.repository = RepositoryRepository(db)
        self.snapshots = SnapshotStore(db)

    # -- submit --------------------------------------------------------------

    def submit(self, repository_id: str) -> AnalysisJob:
        """Durably enqueue analysis for a repository, idempotently.

        Duplicate submissions never create duplicate work: an already-completed
        snapshot short-circuits to a ``completed`` job, and a still-active job
        for the same identity is returned unchanged (the partial unique index
        also enforces this at the database level for concurrent submits).
        """

        record = self._get_record(repository_id)
        revision_value = self._require_revision(record)

        # 1. Already-sealed snapshot for this exact identity ⇒ idempotent-complete.
        completed = self.snapshots.find_completed_for_owner(
            owner_id=self.owner_id,
            repository_id=record.id,
            revision_value=revision_value,
            schema_version=ANALYSIS_SCHEMA_VERSION,
            producer_version_set=ANALYSIS_PRODUCER_VERSION_SET,
            config_hash=ANALYSIS_CONFIG_HASH,
        )
        if completed is not None:
            existing = self._job_for_snapshot(record.id, completed.snapshot_id)
            if existing is not None:
                return self._reconcile_completed_job(record, existing, completed)
            return self._insert_completed_job(record, completed)

        # 2. An active (queued/running) job for this identity already exists.
        active = self._active_job(record.id, ANALYSIS_CONFIG_HASH)
        if active is not None:
            return active

        # 3. No completed snapshot and no active job ⇒ enqueue a fresh one.
        return self._insert_queued_job(record, ANALYSIS_CONFIG_HASH)

    # -- status --------------------------------------------------------------

    def status(self, repository_id: str) -> AnalysisJob | None:
        """Return the most recent job for a repository, or ``None`` if none.

        ``None`` means no analysis job has ever been submitted; the route layer
        treats that as "not started" (surfaced as ``queued``).
        """

        self._get_record(repository_id)
        return self._latest_job(repository_id)

    # -- cancel --------------------------------------------------------------

    def cancel(self, repository_id: str) -> AnalysisJob:
        """Cancel the current job cooperatively.

        A ``queued`` job (never claimed) transitions straight to ``cancelled``.
        A ``running`` job is flagged ``cancel_requested`` and left running; the
        worker observes the flag at its next stage boundary and performs the
        actual transition once it stops. A terminal job — or no job at all —
        has nothing to cancel and raises ``ConflictServiceError`` (409).
        """

        self._get_record(repository_id)
        job = self._latest_job(repository_id)
        if job is None:
            raise ConflictServiceError(
                "No analysis job to cancel.", {"repositoryId": repository_id}
            )
        return self._cancel_job(job)

    def _cancel_job(self, job: AnalysisJob) -> AnalysisJob:
        """Cancel ``job`` without overwriting a concurrent claim/terminal state."""

        if job.status == "queued":
            now = _utcnow()
            result = self.db.execute(
                update(AnalysisJob)
                .where(
                    AnalysisJob.id == job.id,
                    AnalysisJob.owner_id == self.owner_id,
                    AnalysisJob.status == "queued",
                )
                .values(
                    status="cancelled",
                    cancel_requested=False,
                    worker_id=None,
                    lease_expires_at=None,
                    next_attempt_at=None,
                    completed_at=now,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            if result.rowcount != 0:
                return self._reload_job(job.id)
            # A worker may have claimed the queued row between the read and the
            # guarded update. Re-read and request cooperative cancellation from
            # the actual running owner instead of overwriting its claim.
            job = self._reload_job(job.id)
        if job.status == "running":
            now = _utcnow()
            result = self.db.execute(
                update(AnalysisJob)
                .where(
                    AnalysisJob.id == job.id,
                    AnalysisJob.owner_id == self.owner_id,
                    AnalysisJob.status == "running",
                )
                .values(cancel_requested=True, updated_at=now)
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            if result.rowcount != 0:
                return self._reload_job(job.id)
            # Completion/failure/cancellation may have won the race. The
            # terminal row is authoritative and must never be overwritten.
            job = self._reload_job(job.id)
        raise ConflictServiceError(
            "Analysis job is not in a cancellable state.",
            {"repositoryId": job.repository_id, "status": job.status},
        )

    # -- internals -----------------------------------------------------------

    def _get_record(self, repository_id: str) -> RepositoryRecord:
        # Owner-scoped: get_for_owner returns None for both a missing repository
        # and one owned by another user, so a cross-user request gets the same
        # 404 as a missing one and never learns the resource exists.
        record = self.repository.get_for_owner(repository_id, self.owner_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": repository_id})
        return record

    @staticmethod
    def _require_revision(record: RepositoryRecord) -> str:
        if record.revision_kind is None or record.revision_value is None:
            raise ServiceError(
                "Repository has no analyzable revision.", {"repositoryId": record.id}
            )
        return record.revision_value

    def _latest_job(self, repository_id: str) -> AnalysisJob | None:
        return self.db.scalars(
            select(AnalysisJob)
            .where(
                AnalysisJob.repository_id == repository_id,
                AnalysisJob.owner_id == self.owner_id,
            )
            .order_by(AnalysisJob.created_at.desc())
            .limit(1)
        ).first()

    def _reload_job(self, job_id: str) -> AnalysisJob:
        self.db.expire_all()
        job = self.db.get(AnalysisJob, job_id)
        if job is None or job.owner_id != self.owner_id:
            raise ConflictServiceError("No analysis job to cancel.")
        return job

    def _active_job(self, repository_id: str, config_hash: str) -> AnalysisJob | None:
        return self.db.scalars(
            select(AnalysisJob)
            .where(
                AnalysisJob.repository_id == repository_id,
                AnalysisJob.owner_id == self.owner_id,
                AnalysisJob.config_hash == config_hash,
                AnalysisJob.status.in_(("queued", "running")),
            )
            .order_by(AnalysisJob.created_at.desc())
            .limit(1)
        ).first()

    def _job_for_snapshot(self, repository_id: str, snapshot_id: str) -> AnalysisJob | None:
        return self.db.scalars(
            select(AnalysisJob)
            .where(
                AnalysisJob.repository_id == repository_id,
                AnalysisJob.owner_id == self.owner_id,
                AnalysisJob.snapshot_id == snapshot_id,
            )
            .order_by(AnalysisJob.created_at.desc())
            .limit(1)
        ).first()

    def _insert_queued_job(self, record: RepositoryRecord, config_hash: str) -> AnalysisJob:
        job = AnalysisJob(
            id=str(uuid4()),
            repository_id=record.id,
            owner_id=self.owner_id,
            revision_kind=record.revision_kind,
            revision_value=record.revision_value,
            config_hash=config_hash,
            status="queued",
            attempt=0,
        )
        self.db.add(job)
        try:
            self.db.commit()
        except IntegrityError:
            # A concurrent submit won the partial unique index on the active
            # identity. Reconcile by returning the winner's row rather than
            # erroring the caller — duplicate submissions never fail.
            self.db.rollback()
            active = self._active_job(record.id, config_hash)
            if active is not None:
                return active
            raise
        self.db.refresh(job)
        return job

    def _reconcile_completed_job(
        self, record: RepositoryRecord, job: AnalysisJob, snapshot: RiSnapshot
    ) -> AnalysisJob:
        """Make a sealed snapshot authoritative over any non-completed job row."""

        if (
            job.status == "completed"
            and job.stage == "completed"
            and job.progress == 100
            and job.snapshot_id == snapshot.snapshot_id
            and not job.cancel_requested
            and job.worker_id is None
            and job.lease_expires_at is None
            and job.next_attempt_at is None
            and job.error_code is None
            and job.error_message is None
            and job.completed_at is not None
            and record.status == "completed"
            and record.analysis_stage == "completed"
            and record.analysis_progress == 100
            and record.error_message is None
            and record.analysed_at is not None
        ):
            return job
        now = _utcnow()
        completed_at = snapshot.sealed_at or now
        job.status = "completed"
        job.stage = "completed"
        job.progress = 100
        job.snapshot_id = snapshot.snapshot_id
        job.cancel_requested = False
        job.worker_id = None
        job.lease_expires_at = None
        job.next_attempt_at = None
        job.error_code = None
        job.error_message = None
        job.started_at = job.started_at or snapshot.created_at
        job.completed_at = completed_at
        job.updated_at = now
        self._complete_repository(record, completed_at)
        self.db.commit()
        self.db.refresh(job)
        return job

    def _insert_completed_job(
        self, record: RepositoryRecord, snapshot: RiSnapshot
    ) -> AnalysisJob:
        now = _utcnow()
        completed_at = snapshot.sealed_at or now
        job = AnalysisJob(
            id=str(uuid4()),
            repository_id=record.id,
            owner_id=self.owner_id,
            revision_kind=record.revision_kind,
            revision_value=record.revision_value,
            config_hash=ANALYSIS_CONFIG_HASH,
            status="completed",
            stage="completed",
            progress=100,
            attempt=0,
            snapshot_id=snapshot.snapshot_id,
            started_at=snapshot.created_at,
            completed_at=completed_at,
        )
        self.db.add(job)
        self._complete_repository(record, completed_at)
        try:
            self.db.commit()
        except IntegrityError:
            # Another submit associated this sealed snapshot while both callers
            # had no job row. The unique snapshot index makes that race safe;
            # return the winner just like the active-job insertion path.
            self.db.rollback()
            existing = self._job_for_snapshot(record.id, snapshot.snapshot_id)
            if existing is not None:
                return existing
            raise
        self.db.refresh(job)
        return job

    @staticmethod
    def _complete_repository(record: RepositoryRecord, completed_at: datetime) -> None:
        record.status = "completed"
        record.analysis_stage = "completed"
        record.analysis_progress = 100
        record.error_message = None
        record.analysed_at = completed_at
