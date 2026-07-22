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

from sqlalchemy import select
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
                return existing
            return self._insert_completed_job(record, completed.snapshot_id)

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
        if job.status == "queued":
            job.status = "cancelled"
            job.completed_at = _utcnow()
            self.db.commit()
            self.db.refresh(job)
            return job
        if job.status == "running":
            job.cancel_requested = True
            self.db.commit()
            self.db.refresh(job)
            return job
        raise ConflictServiceError(
            "Analysis job is not in a cancellable state.",
            {"repositoryId": repository_id, "status": job.status},
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

    def _insert_completed_job(self, record: RepositoryRecord, snapshot_id: str) -> AnalysisJob:
        now = _utcnow()
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
            snapshot_id=snapshot_id,
            started_at=now,
            completed_at=now,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
