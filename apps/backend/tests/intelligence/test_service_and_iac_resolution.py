"""Resolution of service-interaction and IaC observations (#209).

These resolvers are only allowed to connect facts the extractors already
proved. The tests below pin what they emit, what they refuse to emit, and the
truth class and provenance every emitted edge carries.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.intelligence.resolution import RI_RES_UNRESOLVED, RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base
from app.models.snapshot import RiDerivation, RiDiagnostic, RiEdge, RiEvidence

REVISION = "sha256:" + "c" * 64
SOURCE_PRODUCER = "fixture-extractor"
SOURCE_VERSION = "1.0.0"
RESOLVER_PRODUCER = f"{RelationshipResolver.name}@{RelationshipResolver.version}"


@pytest.fixture()
def session(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'service-resolution.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()


def _store(session):
    owner = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    repository = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name="resolver",
        source="upload",
        revision_kind="upload",
        revision_value=REVISION,
        local_path="/x",
        status="completed",
        file_tree=[],
    )
    session.add(repository)
    session.commit()
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", REVISION),
        producer_version_set=[f"{SOURCE_PRODUCER}@{SOURCE_VERSION}", RESOLVER_PRODUCER],
    )
    return store, snapshot


def _evidence(path: str, line: int = 1) -> Evidence:
    return Evidence(
        path=path,
        start_line=line,
        end_line=line,
        extractor=SOURCE_PRODUCER,
        extractor_version=SOURCE_VERSION,
        logical_line_count=30,
    )


def _node(store, snapshot, kind: str, key: str, *, name=None, path="app/client.py", line=1, properties=None):
    return store.add_node(
        snapshot,
        node_kind=kind,
        stable_key=key,
        name=name,
        properties=properties,
        evidence=[_evidence(path, line)],
    )


def _observation(store, snapshot, *, kind, subject_kind, subject, referent, path="app/client.py", line=1):
    return store.add_observation(
        snapshot,
        observed_kind=kind,
        subject_kind=subject_kind,
        subject_key=subject,
        referent_text=referent,
        ordinal=1,
        evidence=_evidence(path, line),
    )


def _triples(session, snapshot):
    return {
        (edge.subject_key, edge.predicate, edge.object_key)
        for edge in session.scalars(select(RiEdge).where(RiEdge.snapshot_id == snapshot.snapshot_id))
    }


def _diagnostics(session, snapshot):
    return [
        (item.code, item.message)
        for item in session.scalars(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    ]


def _service_graph(store, snapshot):
    """A module, a symbol whose span contains the call, and the service node."""

    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "module", "mod:app")
    _node(store, snapshot, "file", "file:app/client.py")
    store.add_node(
        snapshot,
        node_kind="symbol",
        stable_key="app/client.py::load",
        name="load",
        evidence=[
            Evidence(
                path="app/client.py",
                start_line=4,
                end_line=6,
                extractor=SOURCE_PRODUCER,
                extractor_version=SOURCE_VERSION,
                logical_line_count=30,
            )
        ],
    )
    _node(
        store,
        snapshot,
        "service",
        "svc:https://api.example.com",
        name="https://api.example.com",
        properties={"origin": "https://api.example.com"},
        line=5,
    )


# --- calls_service ----------------------------------------------------------


def test_a_proven_call_resolves_to_the_service_node_for_its_origin(session):
    store, snapshot = _store(session)
    _service_graph(store, snapshot)
    _observation(
        store,
        snapshot,
        kind="http_call",
        subject_kind="module",
        subject="mod:app",
        referent="GET|https://api.example.com|/v1/users",
        line=5,
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.edges_added == 1
    assert result.diagnostics_added == 0
    # Attributed to the symbol whose span contains the call, exactly like a
    # generic ``calls`` reference — not to the whole module.
    assert _triples(session, snapshot) == {
        ("app/client.py::load", "calls_service", "svc:https://api.example.com")
    }


def test_a_call_outside_any_symbol_is_attributed_to_its_module(session):
    store, snapshot = _store(session)
    _service_graph(store, snapshot)
    _observation(
        store,
        snapshot,
        kind="http_call",
        subject_kind="module",
        subject="mod:app",
        referent="POST|https://api.example.com|/v1",
        line=1,
    )

    RelationshipResolver(store).resolve(snapshot)

    assert _triples(session, snapshot) == {("mod:app", "calls_service", "svc:https://api.example.com")}


def test_a_resolved_service_edge_is_evidence_backed_and_derived_from_its_observation(session):
    store, snapshot = _store(session)
    _service_graph(store, snapshot)
    observation = _observation(
        store,
        snapshot,
        kind="http_call",
        subject_kind="module",
        subject="mod:app",
        referent="GET|https://api.example.com|/v1/users",
        line=5,
    )

    RelationshipResolver(store).resolve(snapshot)

    edge = session.scalars(select(RiEdge).where(RiEdge.snapshot_id == snapshot.snapshot_id)).one()
    assert edge.truth_class == "resolved"
    assert edge.producer == RelationshipResolver.name
    assert edge.producer_version == RelationshipResolver.version
    evidence = session.scalars(
        select(RiEvidence).where(RiEvidence.snapshot_id == snapshot.snapshot_id, RiEvidence.edge_ref == edge.id)
    ).all()
    assert [(item.path, item.start_line, item.end_line) for item in evidence] == [("app/client.py", 5, 5)]
    derivations = session.scalars(
        select(RiDerivation).where(
            RiDerivation.snapshot_id == snapshot.snapshot_id, RiDerivation.edge_ref == edge.id
        )
    ).all()
    assert [(item.ref_kind, item.ref_identity) for item in derivations] == [
        ("observation", observation.observation_id)
    ]


def test_an_origin_with_no_service_node_stays_unresolved(session):
    store, snapshot = _store(session)
    _service_graph(store, snapshot)
    _observation(
        store,
        snapshot,
        kind="http_call",
        subject_kind="module",
        subject="mod:app",
        referent="GET|https://other.example.com|/v1",
        line=5,
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.edges_added == 0
    assert _triples(session, snapshot) == set()
    assert _diagnostics(session, snapshot) == [
        (RI_RES_UNRESOLVED, "calls_service target service is absent from the snapshot")
    ]


@pytest.mark.parametrize("referent", ["GET|https://api.example.com", "", "GET||/v1", "not-a-destination"])
def test_a_malformed_destination_referent_is_never_repaired(session, referent):
    store, snapshot = _store(session)
    _service_graph(store, snapshot)
    _observation(
        store,
        snapshot,
        kind="http_call",
        subject_kind="module",
        subject="mod:app",
        referent=referent or None,
        line=5,
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.edges_added == 0
    assert _diagnostics(session, snapshot) == [
        (RI_RES_UNRESOLVED, "calls_service has no parsable destination")
    ]


# --- declares ---------------------------------------------------------------


def test_a_declared_iac_resource_is_attached_to_the_repository(session):
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root", path="docker-compose.yml")
    _node(
        store,
        snapshot,
        "iac_resource",
        "iac:docker-compose.yml::service/api",
        name="api",
        path="docker-compose.yml",
        line=2,
        properties={"resource_type": "service", "manifest_format": "docker-compose", "manifest_path": "docker-compose.yml"},
    )
    _observation(
        store,
        snapshot,
        kind="iac_resource",
        subject_kind="iac_resource",
        subject="iac:docker-compose.yml::service/api",
        referent="service/api",
        path="docker-compose.yml",
        line=2,
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.edges_added == 1
    assert _triples(session, snapshot) == {
        ("repo:root", "declares", "iac:docker-compose.yml::service/api")
    }
    edge = session.scalars(select(RiEdge).where(RiEdge.snapshot_id == snapshot.snapshot_id)).one()
    assert edge.truth_class == "resolved"
    assert edge.object_kind == "iac_resource"


def test_an_iac_observation_without_its_node_stays_unresolved(session):
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root", path="docker-compose.yml")
    _node(store, snapshot, "file", "file:docker-compose.yml", path="docker-compose.yml")
    _observation(
        store,
        snapshot,
        kind="iac_resource",
        subject_kind="file",
        subject="file:docker-compose.yml",
        referent="service/api",
        path="docker-compose.yml",
        line=2,
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.edges_added == 0
    assert _diagnostics(session, snapshot) == [(RI_RES_UNRESOLVED, "iac resource declaration is incomplete")]


# --- lockfile resolutions are not relationship inputs -----------------------


def test_a_lockfile_resolution_never_becomes_a_direct_dependency_edge(session):
    """A pin proves an installed version, not that the repository depends on it."""

    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root", path="package-lock.json")
    _node(store, snapshot, "dependency", "dep:npm:tiny", name="tiny", path="package-lock.json", line=9)
    _observation(
        store,
        snapshot,
        kind="resolution",
        subject_kind="dependency",
        subject="dep:npm:tiny",
        referent="0.1.0",
        path="package-lock.json",
        line=9,
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.edges_added == 0
    # It is retained as an observation rather than downgraded to a diagnostic:
    # nothing about it is unresolved, it simply is not a relationship claim.
    assert result.diagnostics_added == 0
    assert _triples(session, snapshot) == set()


def test_a_manifest_declaration_still_produces_the_direct_dependency_edge(session):
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root", path="package.json")
    _node(store, snapshot, "dependency", "dep:npm:react", name="react", path="package.json", line=4)
    _observation(
        store,
        snapshot,
        kind="dependency",
        subject_kind="dependency",
        subject="dep:npm:react",
        referent="react",
        path="package.json",
        line=4,
    )
    _observation(
        store,
        snapshot,
        kind="resolution",
        subject_kind="dependency",
        subject="dep:npm:react",
        referent="18.3.1",
        path="package-lock.json",
        line=9,
    )

    RelationshipResolver(store).resolve(snapshot)

    assert _triples(session, snapshot) == {("repo:root", "depends_on", "dep:npm:react")}


# --- determinism ------------------------------------------------------------


def test_resolution_is_deterministic_across_repeated_passes(session):
    store, snapshot = _store(session)
    _service_graph(store, snapshot)
    _observation(
        store,
        snapshot,
        kind="http_call",
        subject_kind="module",
        subject="mod:app",
        referent="GET|https://api.example.com|/v1/users",
        line=5,
    )

    first = RelationshipResolver(store).resolve(snapshot)
    triples = _triples(session, snapshot)
    second = RelationshipResolver(store).resolve(snapshot)

    assert (first.edges_added, first.diagnostics_added) == (second.edges_added, second.diagnostics_added)
    assert _triples(session, snapshot) == triples
