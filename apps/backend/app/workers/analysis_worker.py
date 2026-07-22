"""Durable analysis-job execution (#93).

``AnalysisWorker`` claims one queued ``analysis_jobs`` row at a time and runs the
full analysis off the request path: the legacy ``RepositoryIntelligenceEngine``
build (which other consumers still read via ``repo_metadata['intelligence']``)
followed by the evidence-backed extraction pipeline that seals a Repository
Intelligence snapshot.

``run_once`` is the primary unit both the background loop in ``app.main`` and the
test-suite drive; it is synchronous and deterministic. It claims at most one job
with a portable compare-and-swap (no ``SELECT ... FOR UPDATE SKIP LOCKED``), runs
the stages with a cooperative cancellation check between each, and applies a
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

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.extraction.base import ExtractedEvidence
from app.extraction.pipeline import (
    DEFAULT_MAX_SOURCE_BYTES,
    ExtractionPipeline,
    ProducedExtraction,
)
from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence import canonical
from app.intelligence.engine import RepositoryIntelligenceEngine
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


@dataclass
class _StageContext:
    """Mutable state threaded through one job's stage pipeline."""

    session: Session
    job: AnalysisJob
    record: RepositoryRecord | None
    store: SnapshotStore | None = None
    snapshot: RiSnapshot | None = None
    reused: bool = False
    produced: tuple[ProducedExtraction, ...] = field(default_factory=tuple)


class AnalysisWorker:
    """Claim and execute one durable analysis job at a time."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        worker_id: str,
        lease_seconds: int,
        max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.max_source_bytes = max_source_bytes
        self._clock = clock
        self.intelligence = RepositoryIntelligenceEngine()

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
            ("reading-structure", 25, self._stage_legacy),
            ("extracting-modules", 50, self._stage_open_snapshot),
            ("building-dependency-graph", 75, self._stage_extract),
            ("preparing-architecture", 90, self._stage_seal),
        )
        try:
            for stage_name, progress, stage in stages:
                if self._cancel_requested(ctx):
                    self._cancel(ctx)
                    yield ctx
                    return
                stage(ctx)
                self._checkpoint(ctx, stage_name, progress)
                yield ctx
            if self._cancel_requested(ctx):
                self._cancel(ctx)
                yield ctx
                return
            self._complete(ctx)
            yield ctx
        except Exception as exc:  # noqa: BLE001 - bounded retry is the contract
            self._retry_or_fail(ctx, exc)
            yield ctx

    def _stage_legacy(self, ctx: _StageContext) -> None:
        """Run the legacy intelligence build, preserved verbatim from AnalysisService.

        ``from_record`` + ``persist`` populate ``repo_metadata['intelligence']``,
        which the architecture/dependencies/review read endpoints still consume
        directly; this behaviour is unchanged, only moved off the request path.
        """

        record = self._require_record(ctx)
        record.status = "analysing"
        record.analysis_stage = "preparing-architecture"
        record.analysis_progress = 80
        repository_intelligence = self.intelligence.from_record(record)
        self.intelligence.persist(record, repository_intelligence)

    def _stage_open_snapshot(self, ctx: _StageContext) -> None:
        """Open (or reuse) the snapshot for this job's exact semantic identity.

        Submit and execution must key on the identical identity constants or the
        idempotency guarantee breaks, so the shared ``ANALYSIS_*`` constants are
        used here. ``job.snapshot_id`` is recorded as soon as the id exists —
        before any facts or sealing — so a later crash-recovery sweep can find and
        fail an orphaned ``building`` snapshot.
        """

        record = self._require_record(ctx)
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
        sources = self._read_sources(record)
        pipeline = ExtractionPipeline(
            (PythonExtractor(), TypeScriptExtractor()),
            max_source_bytes=self.max_source_bytes,
        )
        ctx.produced = pipeline.run(sources)
        for produced in ctx.produced:
            self._persist_produced(store, snapshot, produced)
        RelationshipResolver(store).resolve(snapshot)

    def _stage_seal(self, ctx: _StageContext) -> None:
        """Seal the building snapshot (commits internally, see the module note)."""

        if ctx.reused:
            return
        assert ctx.store is not None and ctx.snapshot is not None
        ctx.store.seal(ctx.snapshot)

    # -- terminal transitions ------------------------------------------------

    def _complete(self, ctx: _StageContext) -> None:
        """Mark the job (and its repository record) completed.

        This commit is deliberately separate from ``seal``'s commit (see the
        module note); do not merge them.
        """

        job = ctx.job
        now = self._clock()
        job.status = "completed"
        job.stage = "completed"
        job.progress = 100
        job.worker_id = None
        job.lease_expires_at = None
        job.error_code = None
        job.error_message = None
        job.completed_at = now
        job.updated_at = now
        if ctx.record is not None:
            ctx.record.status = "completed"
            ctx.record.analysis_stage = "completed"
            ctx.record.analysis_progress = 100
            ctx.record.error_message = None
            ctx.record.analysed_at = now
        ctx.session.commit()

    def _cancel(self, ctx: _StageContext) -> None:
        """Honour a cooperative cancel: fail any open snapshot, cancel the job."""

        self._fail_open_snapshot(ctx, code=_CANCELLED_CODE)
        job = ctx.job
        now = self._clock()
        job.status = "cancelled"
        job.worker_id = None
        job.lease_expires_at = None
        job.completed_at = now
        job.updated_at = now
        ctx.session.commit()

    def _retry_or_fail(self, ctx: _StageContext, exc: Exception) -> None:
        """Bounded retry: re-queue with backoff, or fail after ``max_attempts``."""

        session = ctx.session
        session.rollback()
        # Rollback expired the in-memory rows; reload from the row that the claim
        # already committed so ``attempt``/``max_attempts`` reflect the database.
        job = session.get(AnalysisJob, ctx.job.id)
        ctx.job = job
        ctx.record = session.get(RepositoryRecord, job.repository_id)
        now = self._clock()
        if job.attempt >= job.max_attempts:
            self._fail_open_snapshot(ctx, code=_ERROR_CODE)
            job.status = "failed"
            job.worker_id = None
            job.lease_expires_at = None
            job.error_code = _ERROR_CODE
            job.error_message = self._error_message(exc)
            job.completed_at = now
            job.updated_at = now
            if ctx.record is not None:
                ctx.record.status = "error"
                ctx.record.analysis_stage = None
                ctx.record.analysis_progress = 0
                ctx.record.error_message = "Repository analysis failed."
            session.commit()
            return
        job.status = "queued"
        job.worker_id = None
        job.lease_expires_at = None
        job.next_attempt_at = now + timedelta(seconds=self._backoff(job.attempt))
        job.error_code = _ERROR_CODE
        job.error_message = self._error_message(exc)
        job.updated_at = now
        session.commit()

    # -- helpers -------------------------------------------------------------

    def _checkpoint(self, ctx: _StageContext, stage: str, progress: int) -> None:
        """Persist stage/progress and renew the lease at a stage boundary."""

        job = ctx.job
        now = self._clock()
        job.stage = stage
        job.progress = progress
        job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
        job.updated_at = now
        ctx.session.commit()

    def _cancel_requested(self, ctx: _StageContext) -> bool:
        return bool(
            ctx.session.scalar(
                select(AnalysisJob.cancel_requested).where(AnalysisJob.id == ctx.job.id)
            )
        )

    def _fail_open_snapshot(self, ctx: _StageContext, *, code: str) -> None:
        """Mark an opened-but-unsealed snapshot ``failed`` (no-op if reused/sealed)."""

        if ctx.store is None or ctx.snapshot is None or ctx.reused:
            return
        snapshot = ctx.session.get(RiSnapshot, ctx.snapshot.snapshot_id)
        if snapshot is not None and snapshot.state == "building":
            ctx.store.mark_failed(snapshot, code=code)

    def _read_sources(self, record: RepositoryRecord) -> Mapping[str, bytes]:
        """Read repository source bytes keyed by normalized repo-relative path.

        Paths come from ``record.file_tree`` (already computed at ingestion) rather
        than a fresh filesystem walk. Each file is read to at most
        ``max_source_bytes + 1`` so an oversized file stays bounded in memory and
        the pipeline emits its documented ``RI-LIMIT-SKIP`` diagnostic.
        """

        root = Path(record.local_path)
        sources: dict[str, bytes] = {}
        for raw_path in self._iter_file_paths(record.file_tree or []):
            try:
                path = canonical.normalize_repo_path(raw_path.lstrip("/"))
            except canonical.PathEscapeError:
                continue
            if not path:
                continue
            try:
                with (root / path).open("rb") as handle:
                    sources[path] = handle.read(self.max_source_bytes + 1)
            except OSError:
                continue
        return sources

    @classmethod
    def _iter_file_paths(cls, nodes: list) -> Iterator[str]:
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            if node.get("type") == "file" and node.get("path"):
                yield str(node["path"])
            children = node.get("children")
            if children:
                yield from cls._iter_file_paths(children)

    def _persist_produced(
        self, store: SnapshotStore, snapshot: RiSnapshot, produced: ProducedExtraction
    ) -> None:
        """Convert one ``ExtractionResult`` into snapshot writes.

        This mirrors the proven benchmark adapter conversion, but writes to the
        production ``SnapshotStore`` instead of building comparison facts. Evidence
        provenance carries the emitting producer, which is a declared member of the
        analysis producer set, so sealing's ``declared ⊇ observed`` check holds.
        """

        result = produced.result
        for node in result.nodes:
            set_array_keys = (
                frozenset({"decorators"})
                if node.properties and "decorators" in node.properties
                else frozenset()
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
    def _error_message(exc: Exception) -> str:
        message = str(exc) or exc.__class__.__name__
        return message[:_MAX_ERROR_MESSAGE]
