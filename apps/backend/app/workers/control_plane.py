"""The analysis queue and control-plane boundary (#324).

``analysis_jobs`` *is* the queue. This module is the explicit boundary around
that fact: everything that decides **which work is eligible** and **who owns
it** lives here, and nothing here knows how a repository is analysed.

The split this module introduces
--------------------------------

Before #324 the claim compare-and-swap, the lease-renewal compare-and-swap, the
expired-lease scan and the ownership predicate were private methods of
``AnalysisWorker``, and the polling/sweep policy that drove them lived in
``app.main``. Ownership was therefore expressible only as "whatever the executor
happens to do", and a second worker process would have had to import the
executor to participate in the queue at all.

``AnalysisControlPlane`` is now the seam:

* **control plane** -- eligibility, claiming, lease renewal, expiry, reclaim,
  ownership-guarded mutation, and observing a cancellation request;
* **executor** (``AnalysisWorker``) -- running a *claimed* job through the
  Repository Intelligence pipeline and deciding its terminal transition.

Why the database and not Redis/Celery
-------------------------------------

The durable ``analysis_jobs`` row is already the authority for job identity,
attempt budget, cancellation and lease expiry, and it is already crash-safe by
idempotent reconciliation (see the ``analysis_worker`` module docstring). A
broker would add a second, weaker source of truth that still could not be
trusted over the row, plus a runtime dependency the deployment does not
otherwise need. The protocol below is the abstraction that makes a different
backing store possible later without another redesign of the claim/lease
contract; it is deliberately not that store.

Portability
-----------

Every mutation is a portable compare-and-swap (``UPDATE ... WHERE <guard>``)
rather than ``SELECT ... FOR UPDATE SKIP LOCKED``, so SQLite development and
PostgreSQL deployment share one code path and one contract. PostgreSQL is the
deployment authority; the one dialect-specific concession is the SQLite
busy-timeout handling in :meth:`DatabaseAnalysisControlPlane.renew`, which is
documented at its site.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, cast

from sqlalchemy import CursorResult, func, or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.base import Executable

from app.models.analysis_job import AnalysisJob

logger = logging.getLogger(__name__)

RenewalOutcome = Literal["renewed", "lost", "deferred"]


def lease_expired(lease_expires_at: datetime, now: datetime) -> bool:
    """Compare SQLite-naive and timezone-aware persisted timestamps safely."""

    if lease_expires_at.tzinfo is None and now.tzinfo is not None:
        lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
    elif lease_expires_at.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return lease_expires_at < now


@dataclass(frozen=True, slots=True)
class JobLease:
    """Proof that ``worker_id`` owns ``job_id`` until ``expires_at``.

    A lease is a *value*, not a handle: holding one asserts nothing on its own.
    Ownership is re-proved by the guard on every mutation
    (:meth:`AnalysisControlPlane.update_owned`), so a stale lease object can
    never be used to write to a job another worker has since reclaimed.
    """

    job_id: str
    worker_id: str
    expires_at: datetime
    attempt: int


@dataclass(frozen=True, slots=True)
class LeaseRenewal:
    """The outcome of one renewal attempt.

    ``deferred`` is neither a failure nor a loss: SQLite serialises writers, so
    a renewal can be impossible *while this same worker's stage holds the write
    lock*. Ownership is unchanged in that case -- and a sweeper is equally
    locked out -- so the pulse is skipped rather than treated as a lost lease.
    """

    outcome: RenewalOutcome
    cancel_requested: bool = False
    expires_at: datetime | None = None

    @property
    def held(self) -> bool:
        return self.outcome == "renewed"

    @property
    def lost(self) -> bool:
        return self.outcome == "lost"


class AnalysisControlPlane(Protocol):
    """Queue ownership for durable analysis jobs.

    Implementations must make every method safe against concurrent workers
    without holding a lock across a call: each is a single compare-and-swap or
    a read, so a worker process can crash between any two calls and leave only
    an expired lease behind.
    """

    def next_eligible_job_id(self, session: Session, *, now: datetime | None = None) -> str | None:
        """The oldest job the queue would hand out next, without claiming it."""
        ...

    def claim(self, session: Session, *, worker_id: str) -> JobLease | None:
        """Take exclusive ownership of the oldest eligible queued job."""
        ...

    def renew(self, session: Session, lease: JobLease) -> LeaseRenewal:
        """Extend ``lease`` and report any cancellation request."""
        ...

    def expired_job_ids(self, session: Session, *, now: datetime | None = None) -> tuple[str, ...]:
        """Ids of running jobs whose lease has lapsed, oldest lapse first."""
        ...

    def reclaim(self, session: Session, job: AnalysisJob, *, worker_id: str) -> JobLease | None:
        """Take ownership of one expired job, or ``None`` if it moved on."""
        ...

    def update_owned(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        values: dict[str, object],
        require_cancel_not_requested: bool = False,
    ) -> bool:
        """Apply ``values`` only while ``worker_id`` still owns the running job."""
        ...

    def cancel_requested(self, session: Session, job_id: str) -> bool:
        """Read the durable cancellation flag for ``job_id``."""
        ...


class DatabaseAnalysisControlPlane:
    """The v1 control plane: the durable ``analysis_jobs`` table itself."""

    def __init__(
        self,
        *,
        lease_seconds: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.lease_seconds = lease_seconds
        self._clock = clock

    def _lease_until(self, now: datetime) -> datetime:
        return now + timedelta(seconds=self.lease_seconds)

    @staticmethod
    def _execute_dml(session: Session, statement: Executable) -> CursorResult[Any]:
        """Execute a guarded UPDATE and expose its ``rowcount``.

        ``Session.execute`` is declared as returning ``Result``, which carries
        no ``rowcount``; DML always produces a ``CursorResult``, and every
        compare-and-swap here decides ownership from exactly that value.
        """

        return cast(CursorResult[Any], session.execute(statement))

    # -- claim ---------------------------------------------------------------

    def next_eligible_job_id(self, session: Session, *, now: datetime | None = None) -> str | None:
        """The oldest job the queue would hand out next, or ``None``.

        Deliberately separate from :meth:`claim`: this read is the half of a
        claim that carries no ownership at all, and naming it makes the race
        window between reading a candidate and winning it explicit -- both to a
        reader and to a test that needs to hold a candidate across another
        worker's claim.
        """

        moment = now if now is not None else self._clock()
        return session.scalar(
            select(AnalysisJob.id)
            .where(
                AnalysisJob.status == "queued",
                or_(AnalysisJob.next_attempt_at.is_(None), AnalysisJob.next_attempt_at <= moment),
            )
            .order_by(AnalysisJob.created_at)
            .limit(1)
        )

    def claim(self, session: Session, *, worker_id: str) -> JobLease | None:
        """Atomically claim the oldest eligible queued job, or return ``None``.

        A portable compare-and-swap rather than ``SELECT ... FOR UPDATE SKIP
        LOCKED``: pick the oldest eligible id, then ``UPDATE ... WHERE id = :id
        AND status='queued'``. The ``status='queued'`` predicate is the atomic
        guard -- two workers racing for the same row see exactly one non-zero
        ``rowcount``; the loser gets ``None`` and polls again. Eligibility also
        honours ``next_attempt_at``, so a job serving retry backoff is invisible
        to the queue until its delay elapses.
        """

        now = self._clock()
        candidate_id = self.next_eligible_job_id(session, now=now)
        if candidate_id is None:
            return None
        expires_at = self._lease_until(now)
        result = self._execute_dml(
            session,
            update(AnalysisJob)
            .where(AnalysisJob.id == candidate_id, AnalysisJob.status == "queued")
            .values(
                status="running",
                worker_id=worker_id,
                lease_expires_at=expires_at,
                started_at=func.coalesce(AnalysisJob.started_at, now),
                attempt=AnalysisJob.attempt + 1,
                next_attempt_at=None,
                updated_at=now,
            ),
        )
        session.commit()
        if result.rowcount == 0:
            # Another worker won the compare-and-swap for this row.
            return None
        claimed = session.get(AnalysisJob, candidate_id)
        if claimed is None:
            return None
        return JobLease(
            job_id=candidate_id,
            worker_id=worker_id,
            expires_at=expires_at,
            attempt=claimed.attempt,
        )

    # -- renew ---------------------------------------------------------------

    def renew(self, session: Session, lease: JobLease) -> LeaseRenewal:
        """Atomically extend ownership and read back the cancellation flag.

        The guard is ``status='running' AND worker_id = <owner>``: a worker that
        has been reclaimed, or whose job reached a terminal state, matches no
        row and is told its lease is ``lost`` instead of writing to a job it no
        longer owns. Renewal and cancellation observation are one statement, so
        a cancellation request accepted between the two can never be missed.
        """

        sqlite_connection: Any = None
        sqlite_busy_timeout: int | None = None

        def _restore_sqlite_timeout() -> None:
            nonlocal sqlite_connection
            connection = sqlite_connection
            if connection is None or sqlite_busy_timeout is None:
                return
            try:
                cursor = connection.cursor()
                cursor.execute(f"PRAGMA busy_timeout = {sqlite_busy_timeout}")
                cursor.close()
            except Exception:  # noqa: BLE001 - discard a modified connection
                session.invalidate()
            finally:
                sqlite_connection = None

        try:
            if session.bind is not None and session.bind.dialect.name == "sqlite":
                driver_connection = session.connection().connection.driver_connection
                # A pooled connection with no live DBAPI connection has no
                # busy timeout to tune; the renewal is still correct, it just
                # waits the configured default like any other statement.
                if driver_connection is not None:
                    sqlite_connection = driver_connection
                    cursor = driver_connection.cursor()
                    sqlite_busy_timeout = int(cursor.execute("PRAGMA busy_timeout").fetchone()[0])
                    # SQLite serializes all writers. If the stage already owns
                    # the database write lock, a sweeper cannot reclaim the job
                    # either, so the renewal must not block stage cleanup
                    # behind that lock.
                    cursor.execute("PRAGMA busy_timeout = 0")
                    cursor.close()
            now = self._clock()
            expires_at = self._lease_until(now)
            row = session.execute(
                update(AnalysisJob)
                .where(
                    AnalysisJob.id == lease.job_id,
                    AnalysisJob.status == "running",
                    AnalysisJob.worker_id == lease.worker_id,
                )
                .values(lease_expires_at=expires_at, updated_at=now)
                .returning(AnalysisJob.cancel_requested)
                .execution_options(synchronize_session=False)
            ).first()
            if row is None:
                _restore_sqlite_timeout()
                session.rollback()
                return LeaseRenewal(outcome="lost")
            _restore_sqlite_timeout()
            session.commit()
            return LeaseRenewal(outcome="renewed", cancel_requested=bool(row[0]), expires_at=expires_at)
        except Exception as exc:  # noqa: BLE001 - classified here, re-raised to the caller
            _restore_sqlite_timeout()
            session.rollback()
            # A SQLite writer prevents every other SQLite writer, including a
            # stale sweeper. Skipping that transient pulse avoids a false retry;
            # PostgreSQL renewals remain fully independent and guarded.
            if session.bind is not None and session.bind.dialect.name == "sqlite" and "locked" in str(exc).lower():
                logger.debug("SQLite analysis lease renewal skipped while the stage held the write lock")
                return LeaseRenewal(outcome="deferred")
            raise
        finally:
            _restore_sqlite_timeout()

    # -- expiry and reclaim --------------------------------------------------

    def expired_job_ids(self, session: Session, *, now: datetime | None = None) -> tuple[str, ...]:
        """Ids of running jobs whose lease has lapsed, oldest lapse first.

        Read-only, and not itself a claim: a caller must still win
        :meth:`reclaim` for each id before acting on it, because another sweeper
        may reconcile the same row between this scan and that call.
        """

        moment = now if now is not None else self._clock()
        return tuple(
            session.scalars(
                select(AnalysisJob.id)
                .where(
                    AnalysisJob.status == "running",
                    AnalysisJob.lease_expires_at.is_not(None),
                    AnalysisJob.lease_expires_at < moment,
                )
                .order_by(AnalysisJob.lease_expires_at, AnalysisJob.created_at)
            )
        )

    def reclaim(self, session: Session, job: AnalysisJob, *, worker_id: str) -> JobLease | None:
        """Take ownership of one expired job, or ``None`` if it moved on.

        The guard pins the *exact* prior owner and lease instant as well as
        requiring the lease to still be lapsed, so an active lease can never be
        stolen: a renewal landing between the scan and this statement moves
        ``lease_expires_at`` and the compare-and-swap matches nothing.
        """

        now = self._clock()
        expires_at = self._lease_until(now)
        result = self._execute_dml(
            session,
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job.id,
                AnalysisJob.status == "running",
                AnalysisJob.worker_id == job.worker_id,
                AnalysisJob.lease_expires_at == job.lease_expires_at,
                AnalysisJob.lease_expires_at < now,
            )
            .values(worker_id=worker_id, lease_expires_at=expires_at, updated_at=now)
            .execution_options(synchronize_session="fetch"),
        )
        if result.rowcount == 0:
            session.rollback()
            return None
        return JobLease(job_id=job.id, worker_id=worker_id, expires_at=expires_at, attempt=job.attempt)

    # -- ownership-guarded mutation ------------------------------------------

    def update_owned(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        values: dict[str, object],
        require_cancel_not_requested: bool = False,
    ) -> bool:
        """Apply ``values`` only while ``worker_id`` owns the running job.

        Returns ``True`` when the guard matched and ``False`` when ownership was
        lost. Transactional recovery from a lost guard belongs to the caller:
        this method neither commits nor rolls back, so the caller can decide
        whether a miss means abandon, cancel, or reconcile.
        """

        ownership = [
            AnalysisJob.id == job_id,
            AnalysisJob.worker_id == worker_id,
            AnalysisJob.status == "running",
        ]
        if require_cancel_not_requested:
            ownership.append(AnalysisJob.cancel_requested.is_(False))
        with session.no_autoflush:
            result = self._execute_dml(
                session,
                update(AnalysisJob).where(*ownership).values(**values).execution_options(synchronize_session="fetch"),
            )
        return bool(result.rowcount)

    # -- cancellation --------------------------------------------------------

    def cancel_requested(self, session: Session, job_id: str) -> bool:
        """Read the durable cancellation flag for ``job_id``.

        Cancellation is observed from the row rather than carried on the lease,
        so a request accepted by the API after this worker claimed the job is
        still seen at the next cooperative check.
        """

        return bool(session.scalar(select(AnalysisJob.cancel_requested).where(AnalysisJob.id == job_id)))
