from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.pipeline import ExtractionPipeline
from app.extraction.python import PythonExtractor
from app.intelligence import canonical
from app.intelligence.snapshot_store import (
    Evidence,
    Revision,
    SnapshotAlreadySealedError,
    SnapshotImmutableError,
    SnapshotSealError,
    SnapshotStateError,
    SnapshotStore,
    edge_ref,
    node_ref,
    observation_ref,
)
from app.models import (
    RepositoryRecord,
    RiDerivation,
    RiDiagnostic,
    RiEdge,
    RiEvidence,
    RiNode,
    RiSnapshot,
    User,
)
from app.models.base import Base

UPLOAD_REVISION = "sha256:" + "a" * 64
PRODUCERS = ["inventory@1.0.0", "resolver@1.0.0", "classifier@1.0.0"]


@pytest.fixture()
def db(tmp_path):
    # These snapshot tables rely on foreign-key enforcement; SQLite only honors
    # it when this listener is registered on the Engine class (idempotent).
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'snapshots.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session, factory
    engine.dispose()


def _owner(session: Session, email: str = "owner@example.com") -> User:
    owner = User(id=str(uuid4()), email=email, password_hash=None)
    session.add(owner)
    session.commit()
    return owner


def _repository(
    session: Session,
    owner: User,
    *,
    revision_value: str = UPLOAD_REVISION,
    source: str = "upload",
    metadata: dict | None = None,
) -> RepositoryRecord:
    kind = "upload" if revision_value.startswith("sha256:") else "git"
    record = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name=f"repo-{uuid4().hex[:6]}",
        source=source,
        source_url="https://github.com/example/repo" if source == "github" else None,
        branch="main" if source == "github" else None,
        revision_kind=kind,
        revision_value=revision_value,
        revision_ref="refs/heads/main" if kind == "git" else None,
        local_path="/stored/revision",
        status="completed",
        repo_metadata=metadata,
        file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def _evidence(
    path: str,
    start: int = 1,
    end: int = 1,
    *,
    producer: str = "inventory",
    version: str = "1.0.0",
    logical_lines: int = 100,
) -> Evidence:
    return Evidence(
        path=path,
        start_line=start,
        end_line=end,
        extractor=producer,
        extractor_version=version,
        logical_line_count=logical_lines,
    )


def _populate(
    store: SnapshotStore,
    snapshot: RiSnapshot,
    *,
    reverse_evidence: bool = False,
    logical_lines: int = 100,
):
    root_evidence = [
        _evidence("README.md", 1, 2, logical_lines=logical_lines),
        _evidence("README.md", 4, 4, logical_lines=logical_lines),
    ]
    if reverse_evidence:
        root_evidence.reverse()
    store.add_node(
        snapshot,
        node_kind="repository",
        stable_key="repo:root",
        name="repository",
        evidence=root_evidence,
    )
    store.add_node(
        snapshot,
        node_kind="file",
        stable_key="file:src/main.py",
        name="main.py",
        language="python",
        evidence=[_evidence("src/main.py", 1, 20, logical_lines=logical_lines)],
    )
    observation = store.add_observation(
        snapshot,
        observed_kind="contains",
        subject_kind="repository",
        subject_key="repo:root",
        referent_text="src/main.py",
        evidence=_evidence("src/main.py", 1, 20, logical_lines=logical_lines),
    )
    edge = store.add_edge(
        snapshot,
        subject_kind="repository",
        subject_key="repo:root",
        predicate="contains",
        object_kind="file",
        object_key="file:src/main.py",
        producer="resolver",
        producer_version="1.0.0",
        evidence=[_evidence("src/main.py", 1, 20, producer="resolver", logical_lines=logical_lines)],
        derived_from=[observation_ref(observation.observation_id)],
    )
    store.add_assertion(
        snapshot,
        subject_kind="file",
        subject_key="file:src/main.py",
        predicate="classified_as",
        value={"classification": "entrypoint", "confidence": "heuristic"},
        producer="classifier",
        producer_version="1.0.0",
        derived_from=[node_ref("file:src/main.py"), edge_ref(edge.edge_id)],
    )


def _begin(store: SnapshotStore, repository: RepositoryRecord, **kwargs) -> RiSnapshot:
    return store.begin(
        repository_id=repository.id,
        revision=Revision(repository.revision_kind, repository.revision_value, repository.revision_ref),
        producer_version_set=kwargs.pop("producer_version_set", PRODUCERS),
        **kwargs,
    )


def _seal(store: SnapshotStore, repository: RepositoryRecord, **kwargs) -> RiSnapshot:
    snapshot = _begin(store, repository, **kwargs)
    _populate(store, snapshot)
    return store.seal(snapshot)


def test_semantic_identity_reuse_new_inputs_and_failed_attempts(db):
    session, _ = db
    owner = _owner(session)
    repository = _repository(session, owner)
    store = SnapshotStore(session)
    sealed = _seal(store, repository)

    reused, was_reused = store.get_or_reuse(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=list(reversed(PRODUCERS)) + [PRODUCERS[0]],
    )
    assert was_reused is True
    assert reused.snapshot_id == sealed.snapshot_id

    changed_config, reused_config = store.get_or_reuse(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=PRODUCERS,
        config={"pipeline": ["extract", "resolve"]},
    )
    assert reused_config is False and changed_config.state == "building"
    store.mark_failed(changed_config, code="RI-INT-FAILURE")
    assert store.find_completed(
        repository_id=repository.id,
        revision_value=UPLOAD_REVISION,
        schema_version="ri.v1",
        producer_version_set=PRODUCERS,
        config_hash=changed_config.config_hash,
    ) is None

    changed_producers = _begin(store, repository, producer_version_set=PRODUCERS + ["new@2.0.0"])
    changed_schema = _begin(store, repository, schema_version="ri.v2")
    assert changed_producers.snapshot_id != sealed.snapshot_id
    assert changed_schema.snapshot_id != sealed.snapshot_id
    assert session.get(RiSnapshot, sealed.snapshot_id).canonical_graph_hash == sealed.canonical_graph_hash
    with pytest.raises(SnapshotSealError, match="does not match"):
        store.begin(
            repository_id=repository.id,
            revision=Revision("upload", UPLOAD_REVISION),
            producer_version_set=PRODUCERS,
            config={"pipeline": ["extract", "resolve"]},
            config_hash=canonical.compute_config_hash({}),
        )


def test_changed_repository_revision_creates_new_record_and_snapshot_without_rewriting_history(db):
    session, _ = db
    owner = _owner(session)
    first_repository = _repository(session, owner, revision_value="sha256:" + "a" * 64)
    first_snapshot = _seal(SnapshotStore(session), first_repository)
    first_hash = first_snapshot.canonical_graph_hash

    second_repository = _repository(session, owner, revision_value="sha256:" + "b" * 64)
    second_snapshot = _seal(SnapshotStore(session), second_repository)

    assert first_repository.id != second_repository.id
    assert first_snapshot.snapshot_id != second_snapshot.snapshot_id
    assert first_snapshot.revision_value != second_snapshot.revision_value
    assert session.get(RiSnapshot, first_snapshot.snapshot_id).canonical_graph_hash == first_hash


def test_revision_must_match_repository_and_owner_scoped_accessors_hide_cross_owner(db):
    session, _ = db
    owner = _owner(session)
    other = _owner(session, "other@example.com")
    repository = _repository(session, owner)
    sealed = _seal(SnapshotStore(session), repository)
    store = SnapshotStore(session)

    with pytest.raises(SnapshotSealError, match="does not match"):
        store.begin(
            repository_id=repository.id,
            revision=Revision("upload", "sha256:" + "b" * 64),
            producer_version_set=PRODUCERS,
        )
    assert store.get_for_owner(sealed.snapshot_id, owner.id) is not None
    assert store.get_for_owner(sealed.snapshot_id, other.id) is None
    assert store.get_for_owner("snap_missing", owner.id) is None
    assert store.find_completed_for_owner(
        owner_id=other.id,
        repository_id=repository.id,
        revision_value=repository.revision_value,
        schema_version=sealed.schema_version,
        producer_version_set=sealed.producer_version_set,
        config_hash=sealed.config_hash,
    ) is None


def test_repository_revision_identity_is_constrained_and_immutable(db):
    session, _ = db
    owner = _owner(session)
    repository = _repository(session, owner)
    with pytest.raises(ValueError, match="immutable"):
        repository.revision_value = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="immutable"):
        repository.revision_kind = "git"

    invalid = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name="invalid",
        source="github",
        revision_kind="git",
        revision_value="NOT-LOWERCASE-HEX".ljust(40, "x"),
        revision_ref="main",
        local_path="/invalid",
        status="completed",
    )
    session.add(invalid)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_provenance_paths_spans_truth_classes_and_declared_arrays_are_enforced(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)

    with pytest.raises(canonical.PathEscapeError):
        store.add_node(
            snapshot,
            node_kind="file",
            stable_key="file:../secret.txt",
            evidence=[_evidence("../secret.txt")],
        )
    with pytest.raises(SnapshotSealError, match="invalid evidence span"):
        store.add_node(
            snapshot,
            node_kind="file",
            stable_key="file:short.py",
            evidence=[_evidence("short.py", 1, 4, logical_lines=3)],
        )
    with pytest.raises(canonical.CanonicalizationError, match="no declared set/order semantics"):
        store.add_node(
            snapshot,
            node_kind="repository",
            stable_key="repo:root",
            properties={"tags": ["one", "two"]},
            evidence=[_evidence("README.md")],
        )
    with pytest.raises(IntegrityError):
        store.add_node(
            snapshot,
            node_kind="repository",
            stable_key="repo:root",
            truth_class="generated",
            evidence=[_evidence("README.md")],
        )
    session.rollback()


def test_unresolved_and_cyclic_derivations_fail_and_never_become_authoritative(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)

    unresolved = _begin(store, repository, config={"attempt": "unresolved"})
    store.add_node(
        unresolved,
        node_kind="repository",
        stable_key="repo:root",
        evidence=[_evidence("README.md")],
    )
    store.add_assertion(
        unresolved,
        subject_kind="repository",
        subject_key="repo:root",
        predicate="classified_as",
        value={"classification": "service"},
        producer="classifier",
        producer_version="1.0.0",
        derived_from=[node_ref("file:missing.py")],
    )
    with pytest.raises(SnapshotSealError, match="does not resolve"):
        store.seal(unresolved)
    assert unresolved.state == "failed"

    cyclic = _begin(store, repository, config={"attempt": "cycle"})
    store.add_node(cyclic, node_kind="repository", stable_key="repo:root", evidence=[_evidence("README.md")])
    for path in ("a.py", "b.py"):
        store.add_node(
            cyclic,
            node_kind="file",
            stable_key=f"file:{path}",
            evidence=[_evidence(path)],
        )
    obs_a = store.add_observation(
        cyclic,
        observed_kind="contains",
        subject_kind="repository",
        subject_key="repo:root",
        referent_text="a.py",
        evidence=_evidence("a.py"),
    )
    obs_b = store.add_observation(
        cyclic,
        observed_kind="contains",
        subject_kind="repository",
        subject_key="repo:root",
        referent_text="b.py",
        evidence=_evidence("b.py"),
    )
    edge_a_id = canonical.compute_edge_id("repo:root", "contains", "file:a.py")
    edge_b_id = canonical.compute_edge_id("repo:root", "contains", "file:b.py")
    store.add_edge(
        cyclic,
        subject_kind="repository",
        subject_key="repo:root",
        predicate="contains",
        object_kind="file",
        object_key="file:a.py",
        producer="resolver",
        producer_version="1.0.0",
        evidence=[_evidence("a.py", producer="resolver")],
        derived_from=[observation_ref(obs_a.observation_id), edge_ref(edge_b_id)],
    )
    store.add_edge(
        cyclic,
        subject_kind="repository",
        subject_key="repo:root",
        predicate="contains",
        object_kind="file",
        object_key="file:b.py",
        producer="resolver",
        producer_version="1.0.0",
        evidence=[_evidence("b.py", producer="resolver")],
        derived_from=[observation_ref(obs_b.observation_id), edge_ref(edge_a_id)],
    )
    with pytest.raises(SnapshotSealError, match="cycle"):
        store.seal(cyclic)
    assert cyclic.state == "failed"


def test_fatal_diagnostic_fails_snapshot_but_nonfatal_diagnostic_can_seal(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    fatal = _begin(store, repository, config={"attempt": "fatal"})
    store.add_diagnostic(
        fatal,
        code="RI-INT-FAILURE",
        category="internal failure",
        severity="fatal",
        message="The pipeline could not produce a coherent graph.",
        producer="inventory@1.0.0",
    )
    with pytest.raises(SnapshotSealError, match="fatal diagnostic"):
        store.seal(fatal)
    assert fatal.state == "failed" and fatal.failure_code == "RI-FATAL-DIAGNOSTIC"

    nonfatal = _begin(store, repository, config={"attempt": "warning"})
    _populate(store, nonfatal)
    diagnostic = store.add_diagnostic(
        nonfatal,
        code="RI-RES-UNRESOLVED",
        category="unresolved reference",
        severity="warning",
        message="A reference could not be resolved.",
        producer="resolver@1.0.0",
        path="src/main.py",
        span=(3, 3),
        details={"candidates": ["src/z.py::target", "src/a.py::target", "src/a.py::target"]},
    )
    assert diagnostic.details["candidates"] == ["src/a.py::target", "src/z.py::target"]
    assert store.seal(nonfatal).state == "completed"


def test_diagnostics_only_real_extraction_emits_root_and_seals(db):
    """A non-fatal parse error must not violate the mandatory root invariant."""

    session, _ = db
    repository = _repository(session, _owner(session))
    runs = ExtractionPipeline((PythonExtractor(),)).run(
        {"src/broken.py": b"def broken(:\n    return\n"}
    )
    producers = [run.producer for run in runs]
    store = SnapshotStore(session)
    snapshot = _begin(store, repository, producer_version_set=producers)

    for run in runs:
        for node in run.result.nodes:
            store.add_node(
                snapshot,
                node_kind=node.node_kind,
                stable_key=node.stable_key,
                name=node.name,
                language=node.language,
                properties=node.properties,
                evidence=[
                    Evidence(
                        path=evidence.path,
                        start_line=evidence.start_line,
                        end_line=evidence.end_line,
                        extractor=run.producer_name,
                        extractor_version=run.producer_version,
                        logical_line_count=evidence.logical_line_count,
                        granularity=evidence.granularity,
                    )
                    for evidence in node.evidence
                ],
            )
        for diagnostic in run.result.diagnostics:
            store.add_diagnostic(
                snapshot,
                code=diagnostic.code,
                category=diagnostic.category,
                severity=diagnostic.severity,
                message=diagnostic.message,
                producer=run.producer,
                path=diagnostic.path,
                span=diagnostic.span,
                subject=diagnostic.subject,
                details=diagnostic.details,
            )

    assert [node.stable_key for run in runs for node in run.result.nodes] == ["repo:root"]
    assert [diagnostic.code for run in runs for diagnostic in run.result.diagnostics] == ["RI-SRC-MALFORMED"]
    assert store.seal(snapshot).state == "completed"


def test_every_completed_snapshot_mutation_route_is_rejected(db):
    session, factory = db
    repository = _repository(session, _owner(session))
    sealed = _seal(SnapshotStore(session), repository)
    snapshot_id = sealed.snapshot_id
    session.close()

    with factory() as isolated:
        snapshot = isolated.get(RiSnapshot, snapshot_id)
        snapshot.actual_producers.append("tampered@9.9.9")
        with pytest.raises(SnapshotImmutableError):
            isolated.commit()
        isolated.rollback()

    with factory() as isolated:
        node = isolated.scalars(select(RiNode).where(RiNode.snapshot_id == snapshot_id)).first()
        node.name = "tampered"
        with pytest.raises(SnapshotImmutableError):
            isolated.commit()
        isolated.rollback()

    with factory() as isolated:
        node = isolated.scalars(select(RiNode).where(RiNode.snapshot_id == snapshot_id)).first()
        isolated.delete(node)
        with pytest.raises(SnapshotImmutableError):
            isolated.commit()
        isolated.rollback()

    with factory() as isolated:
        isolated.add(
            RiDiagnostic(
                snapshot_id=snapshot_id,
                code="RI-TEST",
                category="internal failure",
                severity="info",
                message="late write",
                producer="inventory@1.0.0",
            )
        )
        with pytest.raises(SnapshotImmutableError):
            isolated.commit()
        isolated.rollback()

    with factory() as isolated:
        with pytest.raises(SnapshotImmutableError):
            isolated.execute(update(RiNode).where(RiNode.snapshot_id == snapshot_id).values(name="bulk"))

    with factory() as isolated:
        snapshot = isolated.get(RiSnapshot, snapshot_id)
        isolated.delete(snapshot)
        with pytest.raises(SnapshotImmutableError):
            isolated.commit()


def test_database_uniqueness_foreign_keys_and_same_snapshot_provenance(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    first = _begin(store, repository, config={"attempt": "first"})
    second = _begin(store, repository, config={"attempt": "second"})
    node_one = store.add_node(first, node_kind="repository", stable_key="repo:root", evidence=[_evidence("README.md")])
    node_two = store.add_node(second, node_kind="repository", stable_key="repo:root", evidence=[_evidence("README.md")])
    session.commit()

    session.add(RiNode(snapshot_id=first.snapshot_id, stable_key="repo:root", node_kind="repository", truth_class="observed"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.add(
        RiEvidence(
            snapshot_id=first.snapshot_id,
            node_ref=node_two.id,
            path="README.md",
            start_line=1,
            end_line=1,
            granularity="span",
            extractor="inventory",
            extractor_version="1.0.0",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert node_one.snapshot_id != node_two.snapshot_id

    session.add(
        RiSnapshot(
            snapshot_id=f"snap_{uuid4().hex}",
            repository_id=repository.id,
            revision_kind="upload",
            revision_value="sha256:" + "c" * 64,
            revision_ref=None,
            schema_version="ri.v1",
            producer_version_set=[],
            producer_set_hash=canonical.producer_set_hash([]),
            config_hash=canonical.compute_config_hash({}),
            state="building",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_equivalent_concurrent_attempts_allow_only_one_completed_snapshot(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    first = _begin(store, repository)
    second = _begin(store, repository)
    _populate(store, first)
    _populate(store, second, reverse_evidence=True)
    sealed = store.seal(first)
    with pytest.raises(SnapshotAlreadySealedError) as error:
        store.seal(second)
    assert error.value.existing.snapshot_id == sealed.snapshot_id
    assert session.scalar(
        select(func.count()).select_from(RiSnapshot).where(RiSnapshot.state == "completed")
    ) == 1


def test_duplicate_semantic_edges_collapse_and_union_normalized_provenance(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[_evidence("README.md")])
    store.add_node(
        snapshot,
        node_kind="file",
        stable_key="file:main.py",
        evidence=[_evidence("main.py", 1, 10)],
    )
    first_observation = store.add_observation(
        snapshot,
        observed_kind="contains",
        subject_kind="repository",
        subject_key="repo:root",
        referent_text="main.py",
        ordinal=1,
        evidence=_evidence("main.py", 1, 1),
    )
    second_observation = store.add_observation(
        snapshot,
        observed_kind="contains",
        subject_kind="repository",
        subject_key="repo:root",
        referent_text="main.py",
        ordinal=2,
        evidence=_evidence("main.py", 7, 7),
    )
    first_edge = store.add_edge(
        snapshot,
        subject_kind="repository",
        subject_key="repo:root",
        predicate="contains",
        object_kind="file",
        object_key="file:main.py",
        producer="resolver",
        producer_version="1.0.0",
        evidence=[_evidence("main.py", 1, 1, producer="resolver")],
        derived_from=[observation_ref(first_observation.observation_id)],
    )
    second_edge = store.add_edge(
        snapshot,
        subject_kind="repository",
        subject_key="repo:root",
        predicate="contains",
        object_kind="file",
        object_key="file:main.py",
        producer="resolver",
        producer_version="1.0.0",
        evidence=[_evidence("main.py", 7, 7, producer="resolver")],
        derived_from=[observation_ref(second_observation.observation_id)],
    )
    assert first_edge.id == second_edge.id
    assert session.scalar(
        select(func.count()).select_from(RiEdge).where(RiEdge.snapshot_id == snapshot.snapshot_id)
    ) == 1
    assert session.scalar(
        select(func.count()).select_from(RiEvidence).where(RiEvidence.edge_ref == first_edge.id)
    ) == 2
    assert session.scalar(
        select(func.count()).select_from(RiDerivation).where(RiDerivation.edge_ref == first_edge.id)
    ) == 2
    assert store.seal(snapshot).state == "completed"


def test_equivalent_graphs_hash_identically_across_insertion_orders_and_repo_ids(db):
    session, _ = db
    owner = _owner(session)
    first_repo = _repository(session, owner)
    second_repo = _repository(session, owner)
    first = _begin(SnapshotStore(session), first_repo)
    _populate(SnapshotStore(session), first, reverse_evidence=False)
    first = SnapshotStore(session).seal(first)
    second = _begin(SnapshotStore(session), second_repo)
    _populate(SnapshotStore(session), second, reverse_evidence=True)
    second = SnapshotStore(session).seal(second)
    assert first.repository_id != second.repository_id
    assert first.canonical_graph_hash == second.canonical_graph_hash


def test_legacy_regex_metadata_is_not_promoted_into_ri_v1_facts(db):
    session, _ = db
    repository = _repository(
        session,
        _owner(session),
        metadata={"intelligence": {"nodes": [{"id": "regex-node"}], "relationships": []}},
    )
    snapshot = _begin(SnapshotStore(session), repository)
    assert session.scalar(
        select(func.count()).select_from(RiNode).where(RiNode.snapshot_id == snapshot.snapshot_id)
    ) == 0
    assert repository.repo_metadata["intelligence"]["nodes"][0]["id"] == "regex-node"


def test_store_rejects_writes_after_failed_snapshot(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    store.mark_failed(snapshot, code="RI-INT-FAILURE")
    snapshot.state = "completed"
    snapshot.canonical_graph_hash = "sha256:" + "f" * 64
    snapshot.sealed_at = datetime.now(UTC)
    with pytest.raises(SnapshotStateError, match="must go through SnapshotStore"):
        session.commit()
    session.rollback()
    with pytest.raises(SnapshotStateError):
        store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[_evidence("README.md")])


def _single_evidence(session: Session, snapshot: RiSnapshot) -> RiEvidence:
    return session.scalars(
        select(RiEvidence).where(RiEvidence.snapshot_id == snapshot.snapshot_id)
    ).one()


def test_post_insert_span_mutation_beyond_logical_lines_cannot_seal_and_fails(db):
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
    # Stretch a persisted span past the single logical line it was allowed.
    _single_evidence(session, snapshot).end_line = 999

    with pytest.raises(SnapshotSealError, match="not bounded by"):
        store.seal(snapshot)

    assert snapshot.state == "failed"
    assert session.scalar(
        select(func.count()).select_from(RiSnapshot).where(RiSnapshot.state == "completed")
    ) == 0
    # The rejected mutation never reached the persisted row.
    assert _single_evidence(session, snapshot).end_line == 1


def test_post_insert_traversing_evidence_path_cannot_seal_and_fails(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    store.add_node(
        snapshot,
        node_kind="repository",
        stable_key="repo:root",
        evidence=[_evidence("README.md", 1, 1)],
    )
    # A traversal survives the DB's leading-slash check but must never seal.
    _single_evidence(session, snapshot).path = "../../etc/passwd"

    with pytest.raises(SnapshotSealError, match="escapes the repository root"):
        store.seal(snapshot)

    assert snapshot.state == "failed"
    assert _single_evidence(session, snapshot).path == "README.md"


def test_post_insert_unnormalized_evidence_path_cannot_seal(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    store.add_node(
        snapshot,
        node_kind="repository",
        stable_key="repo:root",
        evidence=[_evidence("README.md", 1, 1)],
    )
    # Legal to store (no leading slash) but not in normalized form.
    _single_evidence(session, snapshot).path = "./README.md"

    with pytest.raises(SnapshotSealError, match="not in normalized form"):
        store.seal(snapshot)
    assert snapshot.state == "failed"


def test_database_rejects_evidence_span_beyond_logical_line_count(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    node = store.add_node(
        snapshot,
        node_kind="repository",
        stable_key="repo:root",
        evidence=[_evidence("README.md", 1, 1, logical_lines=1)],
    )
    session.commit()

    session.add(
        RiEvidence(
            snapshot_id=snapshot.snapshot_id,
            node_ref=node.id,
            path="README.md",
            start_line=1,
            end_line=999,
            logical_line_count=1,
            granularity="span",
            extractor="inventory",
            extractor_version="1.0.0",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_conflicting_logical_line_count_on_duplicate_evidence_is_rejected(db):
    session, _ = db
    repository = _repository(session, _owner(session))
    store = SnapshotStore(session)
    snapshot = _begin(store, repository)
    with pytest.raises(SnapshotSealError, match="conflicting logical_line_count"):
        store.add_node(
            snapshot,
            node_kind="repository",
            stable_key="repo:root",
            evidence=[
                _evidence("README.md", 1, 1, logical_lines=10),
                _evidence("README.md", 1, 1, logical_lines=20),
            ],
        )
    session.rollback()


def test_get_or_reuse_validates_revision_and_repository_before_reuse(db):
    session, _ = db
    owner = _owner(session)
    repository = _repository(session, owner)
    store = SnapshotStore(session)
    sealed = _seal(store, repository)

    # Malformed: a 'git' request carrying the sealed snapshot's upload value.
    # The old code matched find_completed on value alone and would have reused
    # the upload snapshot; the revision must be validated first.
    with pytest.raises(SnapshotSealError, match="git revisions require"):
        store.get_or_reuse(
            repository_id=repository.id,
            revision=Revision("git", UPLOAD_REVISION),
            producer_version_set=PRODUCERS,
        )

    # A valid but mismatched revision is rejected before the reuse lookup.
    with pytest.raises(SnapshotSealError, match="does not match"):
        store.get_or_reuse(
            repository_id=repository.id,
            revision=Revision("upload", "sha256:" + "b" * 64),
            producer_version_set=PRODUCERS,
        )

    # A valid identical semantic identity still reuses the completed snapshot.
    reused, was_reused = store.get_or_reuse(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=PRODUCERS,
    )
    assert was_reused is True and reused.snapshot_id == sealed.snapshot_id

    # A different valid semantic identity still starts a new building attempt.
    fresh, reused_fresh = store.get_or_reuse(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=PRODUCERS,
        config={"pipeline": ["extract"]},
    )
    assert reused_fresh is False and fresh.state == "building"


def test_logical_line_count_is_internal_and_does_not_alter_the_canonical_hash(db):
    session, _ = db
    owner = _owner(session)
    first_repo = _repository(session, owner)
    second_repo = _repository(session, owner)
    first = _begin(SnapshotStore(session), first_repo)
    _populate(SnapshotStore(session), first, logical_lines=100)
    first = SnapshotStore(session).seal(first)
    second = _begin(SnapshotStore(session), second_repo)
    _populate(SnapshotStore(session), second, logical_lines=500)
    second = SnapshotStore(session).seal(second)

    assert first.state == "completed" and second.state == "completed"
    # Producers reported different logical-line counts for identical graphs; the
    # canonical hash excludes that internal metadata, so the hashes still match.
    assert first.canonical_graph_hash == second.canonical_graph_hash
