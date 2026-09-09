"""Test helpers for driving the durable analysis worker (#93).

The background worker thread is disabled in tests (``ANALYSIS_WORKER_AUTOSTART``
is false in the ``client`` fixture), so tests that trigger ``POST
/analysis/{id}/start`` call :func:`run_analysis_jobs` right afterwards to execute
the enqueued work synchronously and deterministically instead of polling.
"""

from __future__ import annotations


def run_analysis_jobs(worker_id: str = "test-worker") -> int:
    """Claim and run every currently-queued analysis job to completion.

    Returns the number of jobs claimed. Uses the process-wide ``SessionLocal``,
    which the ``client`` fixture has already bound to the test database.
    """

    from app.core.database import SessionLocal
    from app.workers.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(SessionLocal, worker_id=worker_id, lease_seconds=60)
    claimed = 0
    while worker.run_once():
        claimed += 1
    return claimed
