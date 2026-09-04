"""The in-process compatibility runner for the analysis control plane (#324).

#324 requires the current single-worker path to stay available *behind* the new
boundary during migration. This module is that path.

Before this module, ``app.main`` constructed the worker, minted its ownership
token, owned the poll loop, decided the stale-sweep cadence, and joined the
thread on shutdown -- so the API process did not merely *host* a worker, it
*was* the control loop. Nothing outside a FastAPI lifespan could run a worker
without copying that policy.

``AnalysisWorkerRunner`` owns that policy instead. ``app.main`` now only starts
and stops it, and :meth:`AnalysisWorkerRunner.run_forever` is a plain blocking
call, so the same loop a future standalone worker process needs is already
here -- a ``__main__`` that builds a runner and calls ``run_forever`` adds no
new queue policy. Building that deployment is #210's remaining work and is
deliberately not done here.

Threading is an implementation detail of *this* runner, not of the boundary: the
claim/lease contract in ``app.workers.control_plane`` is process-agnostic, and a
separate process would use the identical contract without a daemon thread.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from os import getpid
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.workers.analysis_worker import AnalysisWorker

logger = logging.getLogger(__name__)

#: Empty-queue polls between stale-lease sweeps. Reconciling an expired lease is
#: a scan plus a compare-and-swap per stale row, so it is far cheaper than an
#: analysis but not free; once per N polls keeps recovery prompt without turning
#: an idle worker into a busy sweeper.
DEFAULT_STALE_SWEEP_INTERVAL_POLLS = 10

#: How long ``stop`` waits for the loop thread to leave its current iteration.
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 10.0


def new_worker_id(pid: int | None = None) -> str:
    """Mint a process-observable, globally unique worker ownership token.

    The pid makes an owner traceable to a process in logs; the uuid makes two
    workers in the *same* process (or in two containers that happen to share a
    pid namespace) distinct owners. Uniqueness is what the control plane's
    ownership guards rest on, so it must not depend on the pid alone. The result
    fits ``analysis_jobs.worker_id`` (64 characters).
    """

    return f"analysis-worker-{pid if pid is not None else getpid()}-{uuid4().hex}"


class AnalysisWorkerRunner:
    """Drive one :class:`AnalysisWorker` against the queue until stopped.

    The loop claims and runs one job per iteration and sleeps *only* when the
    queue is empty, so a backlog drains without an artificial poll delay between
    jobs. A failed iteration is logged and the loop continues: one bad job must
    never stop the worker, and the job's own bounded-retry and stale-lease paths
    already decide what happens to it.
    """

    def __init__(
        self,
        worker: AnalysisWorker,
        *,
        poll_interval_seconds: float,
        stale_sweep_interval_polls: int = DEFAULT_STALE_SWEEP_INTERVAL_POLLS,
    ) -> None:
        self.worker = worker
        self.poll_interval_seconds = poll_interval_seconds
        self.stale_sweep_interval_polls = stale_sweep_interval_polls
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def worker_id(self) -> str:
        return self.worker.worker_id

    def sweep_on_start(self) -> None:
        """Reclaim jobs orphaned by a previous hard process exit.

        A crash leaves a running row with a lease nobody will renew. Sweeping
        once at startup recovers those immediately instead of waiting out the
        first periodic sweep. A failure here must not prevent the process from
        starting, so it is logged rather than raised.
        """

        try:
            self.worker.sweep_stale()
        except Exception:  # noqa: BLE001 - stale cleanup must not block startup
            logger.exception("Initial stale analysis-job sweep failed")

    def run_forever(self) -> None:
        """Run the claim/sweep loop on the calling thread until :meth:`stop`.

        This is the whole control loop. :meth:`start` runs it on a daemon thread
        for the in-process path; a standalone worker process would call it
        directly.
        """

        polls_since_sweep = 0
        while not self._stop.is_set():
            try:
                claimed = self.worker.run_once()
                polls_since_sweep += 1
                if polls_since_sweep >= self.stale_sweep_interval_polls:
                    self.worker.sweep_stale()
                    polls_since_sweep = 0
            except Exception:  # noqa: BLE001 - a single bad job must not kill the loop
                logger.exception("Analysis worker iteration failed")
                claimed = False
            if not claimed:
                self._stop.wait(self.poll_interval_seconds)

    def start(self) -> None:
        """Sweep once, then run the loop on a daemon thread."""

        if self._thread is not None:
            raise RuntimeError("analysis worker runner is already started")
        self.sweep_on_start()
        self._stop.clear()
        self._thread = threading.Thread(target=self.run_forever, name="analysis-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS) -> None:
        """Signal the loop and the worker's heartbeats, then join the thread.

        Both signals are needed and ordered: ``_stop`` ends the loop after the
        current iteration, and ``worker.shutdown()`` releases a stage heartbeat
        that would otherwise keep renewing a lease while the process exits. A
        thread still alive after ``timeout`` is a daemon, so it cannot block
        interpreter exit; it is reported rather than killed.
        """

        self._stop.set()
        self.worker.shutdown()
        thread = self._thread
        self._thread = None
        if thread is None:
            return
        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning(
                "Analysis worker loop did not stop within the shutdown timeout",
                extra={"worker_id": self.worker_id, "timeout_seconds": timeout},
            )


def build_analysis_worker(
    settings: Settings,
    session_factory: Callable[[], Session],
    *,
    worker_id: str | None = None,
) -> AnalysisWorker:
    """Construct the configured executor for the durable analysis queue."""

    return AnalysisWorker(
        session_factory,
        worker_id=worker_id or new_worker_id(),
        lease_seconds=settings.analysis_job_lease_seconds,
        max_repository_source_bytes=settings.analysis_max_repository_source_bytes,
        max_process_rss_bytes=settings.analysis_max_process_rss_bytes,
        max_analysis_seconds=settings.analysis_max_duration_seconds,
    )


def build_analysis_worker_runner(
    settings: Settings | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> AnalysisWorkerRunner:
    """Assemble the configured in-process runner.

    Imported lazily by callers that only need it when the worker actually
    autostarts, which keeps the database session factory out of import order for
    processes that never run a worker.
    """

    resolved_settings = settings if settings is not None else get_settings()
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    worker = build_analysis_worker(resolved_settings, session_factory)
    return AnalysisWorkerRunner(
        worker,
        poll_interval_seconds=resolved_settings.analysis_job_poll_interval_seconds,
    )
