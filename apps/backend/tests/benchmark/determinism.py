"""Snapshot determinism over the real SnapshotStore and canonical graph hash.

For each fixture flagged ``deterministic``, this builds the fixture's observed
**node** graph twice through the *real* :class:`app.intelligence.snapshot_store.SnapshotStore`
— different owner, different repository id, reversed node and evidence insertion
order — and requires the two sealed ``canonical_graph_hash`` values to match. It
also recomputes the pure :func:`app.intelligence.canonical.compute_canonical_graph_hash`
over the same nodes in shuffled order as an independent ordering-independence
check. Both use the product's own hash; the benchmark never substitutes one of
its own (Issue #94 "Do not replace the canonical hash with a benchmark-specific
hash").

Edge / observation / assertion determinism is already proven by the #88
persistence suite; the benchmark's contribution is proving the real pipeline is
deterministic over the golden corpus's node graphs, and reporting *both* hashes
when it is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.intelligence import canonical
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base

from benchmark.loader import LoadedFixture
from benchmark.sourcefiles import logical_line_count_of_bytes

SCHEMA_VERSION = canonical.SCHEMA_VERSION


@dataclass(frozen=True)
class DeterminismResult:
    fixture_id: str
    sealed_hash_a: str
    sealed_hash_b: str
    pure_hash_a: str
    pure_hash_b: str

    @property
    def deterministic(self) -> bool:
        return self.sealed_hash_a == self.sealed_hash_b and self.pure_hash_a == self.pure_hash_b


def _node_facts(fixture: LoadedFixture) -> list:
    return [expected for expected in fixture.expected if expected.group == "nodes"]


def _evidence_for(fixture: LoadedFixture, span) -> Evidence:
    data = (fixture.directory / span.path).read_bytes()
    return Evidence(
        path=span.path,
        start_line=span.start_line,
        end_line=span.end_line,
        extractor=span.extractor,
        extractor_version=span.extractor_version,
        logical_line_count=logical_line_count_of_bytes(data),
        granularity=span.granularity,
    )


def _make_repository(session: Session, owner: User, revision_value: str) -> RepositoryRecord:
    record = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name=f"bench-{uuid4().hex[:6]}",
        source="upload",
        revision_kind="upload",
        revision_value=revision_value,
        revision_ref=None,
        local_path="/stored/revision",
        status="completed",
        file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def _seal_node_graph(session: Session, fixture: LoadedFixture, *, reverse: bool) -> str:
    owner = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    repository = _make_repository(session, owner, fixture.revision_value())
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", fixture.revision_value()),
        producer_version_set=list(fixture.producer_version_set),
    )
    nodes = _node_facts(fixture)
    for expected in reversed(nodes) if reverse else nodes:
        fact = expected.fact
        evidence = [_evidence_for(fixture, span) for span in fact.evidence]
        if reverse:
            evidence = list(reversed(evidence))
        store.add_node(
            snapshot,
            node_kind=fact.kind,
            stable_key=fact.subject,
            name=expected.raw.get("name"),
            language=expected.raw.get("language"),
            evidence=evidence,
        )
    return store.seal(snapshot).canonical_graph_hash


def _pure_node_hash(fixture: LoadedFixture, *, shuffle: bool) -> str:
    records = []
    for expected in _node_facts(fixture):
        fact = expected.fact
        evidence = [
            {
                "path": span.path,
                "start_line": span.start_line,
                "end_line": span.end_line,
                "granularity": span.granularity,
                "extractor": span.extractor,
                "extractor_version": span.extractor_version,
            }
            for span in fact.evidence
        ]
        record = {"node_kind": fact.kind, "stable_key": fact.subject, "truth_class": "observed", "evidence": evidence}
        if expected.raw.get("name") is not None:
            record["name"] = expected.raw["name"]
        if expected.raw.get("language") is not None:
            record["language"] = expected.raw["language"]
        records.append(record)
    if shuffle:
        records = list(reversed(records))
        for record in records:
            record["evidence"] = list(reversed(record["evidence"]))
    return canonical.compute_canonical_graph_hash(
        revision_kind="upload",
        revision_value=fixture.revision_value(),
        producer_version_set=list(fixture.producer_version_set),
        config_hash=canonical.compute_config_hash({}),
        nodes=records,
        edges=[],
        assertions=[],
        observations=[],
        diagnostics=[],
        schema_version=SCHEMA_VERSION,
    )


def check_fixture(fixture: LoadedFixture, db_path: Path) -> DeterminismResult:
    """Seal ``fixture``'s node graph twice and confirm the canonical hash is stable."""

    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        with factory() as session:
            sealed_a = _seal_node_graph(session, fixture, reverse=False)
        with factory() as session:
            sealed_b = _seal_node_graph(session, fixture, reverse=True)
    finally:
        engine.dispose()
    return DeterminismResult(
        fixture_id=fixture.fixture_id,
        sealed_hash_a=sealed_a,
        sealed_hash_b=sealed_b,
        pure_hash_a=_pure_node_hash(fixture, shuffle=False),
        pure_hash_b=_pure_node_hash(fixture, shuffle=True),
    )
