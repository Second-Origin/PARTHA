"""Facts of failed snapshots are discarded; completed ones never are (#485)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.intelligence.retention import purge_orphaned_failed_facts, purge_snapshot_facts
from app.intelligence.snapshot_store import SnapshotSealError, SnapshotStore
from app.models.base import Base
from app.models import RiDiagnostic, RiEdge, RiEvidence, RiNode, RiObservation, RiSnapshot

from tests.test_snapshot_persistence import (
    _begin,
    _evidence,
    _owner,
    _populate,
    _repository,
    _seal,
    _single_evidence,
)


@pytest.fixture()
def db(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'retention.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session, None
    engine.dispose()


_FACTS = (RiNode, RiEdge, RiObservation, RiEvidence, RiDiagnostic)


def _fact_count(session, snapshot_id: str) -> int:
    return sum(
        session.scalar(select(func.count()).select_from(table).where(table.snapshot_id == snapshot_id)) or 0
        for table in _FACTS
    )


def test_failing_a_building_snapshot_discards_its_facts_but_keeps_the_row(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    _populate(store, snapshot)
    assert _fact_count(session, snapshot.snapshot_id) > 0

    store.mark_failed(snapshot, code="RI-CANCELLED")

    assert _fact_count(session, snapshot.snapshot_id) == 0
    row = session.scalars(select(RiSnapshot).where(RiSnapshot.snapshot_id == snapshot.snapshot_id)).one()
    assert (row.state, row.failure_code) == ("failed", "RI-CANCELLED")


def test_a_completed_snapshot_is_never_purged(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    sealed = _seal(store, repository)
    before = _fact_count(session, sealed.snapshot_id)
    assert before > 0

    assert purge_snapshot_facts(session, sealed.snapshot_id) == 0
    assert purge_orphaned_failed_facts(session) == 0

    assert _fact_count(session, sealed.snapshot_id) == before


def test_a_building_snapshot_is_not_purged_either(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    _populate(store, snapshot)
    before = _fact_count(session, snapshot.snapshot_id)

    assert purge_snapshot_facts(session, snapshot.snapshot_id) == 0

    assert _fact_count(session, snapshot.snapshot_id) == before


def test_the_sweep_discards_facts_left_by_a_seal_rejection(db):
    """A rejected seal keeps its facts at first (they are the evidence of what
    was rejected); the periodic sweep then discards them."""

    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    store.add_node(
        snapshot,
        node_kind="repository",
        stable_key="repo:root",
        evidence=[_evidence("README.md", 1, 1, logical_lines=1)],
    )
    _single_evidence(session, snapshot).end_line = 999
    with pytest.raises(SnapshotSealError):
        store.seal(snapshot)
    assert snapshot.state == "failed"
    assert _fact_count(session, snapshot.snapshot_id) > 0

    assert purge_orphaned_failed_facts(session) > 0

    assert _fact_count(session, snapshot.snapshot_id) == 0
    assert purge_orphaned_failed_facts(session) == 0  # nothing left to do
