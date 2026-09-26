"""Discard the facts of snapshots that will never be read (#485).

A snapshot that fails or is cancelled keeps its ``ri_snapshots`` row (the
``failure_code`` and the job that pointed at it stay explainable) but every
node, edge, observation, evidence, derivation, assertion and diagnostic it had
written so far is dead weight: consumers only read *completed* snapshots, and a
retry builds a fresh one. On a large repository a cancelled run can leave tens
of megabytes of partial facts behind, and repeated cancels or failures pile up.

Completed snapshots are never touched here. Which of those to keep is a product
decision (an older revision's history is the reason to keep it), so it is
left to the operator.
"""

from __future__ import annotations

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.models.snapshot import (
    RiAssertion,
    RiDerivation,
    RiDiagnostic,
    RiEdge,
    RiEvidence,
    RiNode,
    RiObservation,
    RiSnapshot,
)

#: Children before parents: evidence and derivations reference nodes, edges,
#: observations and assertions, so they go first.
_FACT_TABLES = (RiDerivation, RiEvidence, RiAssertion, RiDiagnostic, RiEdge, RiObservation, RiNode)


def purge_snapshot_facts(db: Session, snapshot_id: str) -> int:
    """Delete every fact of one *failed* snapshot; return the rows removed.

    Refuses anything but ``failed`` so a completed or in-progress snapshot can
    never be emptied by a caller's mistake.
    """

    state = db.scalar(select(RiSnapshot.state).where(RiSnapshot.snapshot_id == snapshot_id))
    if state != "failed":
        return 0
    # ``SnapshotStore`` rejects bulk ORM writes to these tables (they would
    # bypass lifecycle and hash maintenance for a snapshot someone may read).
    # Neither concern applies to a failed snapshot, which is checked above and
    # can never become anything else, so the delete goes straight to the
    # connection rather than through the guarded session route.
    connection = db.connection()
    removed = 0
    for table in _FACT_TABLES:
        removed += connection.execute(delete(table).where(table.snapshot_id == snapshot_id)).rowcount or 0
    db.commit()
    return removed


def purge_orphaned_failed_facts(db: Session, *, limit: int = 20) -> int:
    """Purge facts left by failed snapshots that predate :func:`purge_snapshot_facts`.

    Bounded per call so a large backlog is worked off over several sweeps
    instead of holding the single SQLite writer for one long transaction.
    """

    candidates = db.scalars(
        select(RiSnapshot.snapshot_id)
        .where(
            RiSnapshot.state == "failed",
            exists().where(RiNode.snapshot_id == RiSnapshot.snapshot_id)
            | exists().where(RiObservation.snapshot_id == RiSnapshot.snapshot_id)
            | exists().where(RiDiagnostic.snapshot_id == RiSnapshot.snapshot_id),
        )
        .limit(limit)
    ).all()
    return sum(purge_snapshot_facts(db, snapshot_id) for snapshot_id in candidates)
