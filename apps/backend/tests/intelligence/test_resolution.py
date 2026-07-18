from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base
from app.models.snapshot import RiDiagnostic, RiEdge


REVISION = "sha256:" + "b" * 64
SOURCE_PRODUCER = "fixture-extractor"
SOURCE_VERSION = "1.0.0"
RESOLVER_PRODUCER = "relationship-resolver@1.0.0"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "resolution"


@pytest.fixture()
def session(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'resolution.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()


def _store(session, producer_version_set: list[str] | None = None):
    owner = User(id=str(uuid4()), email="resolver@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    repository = RepositoryRecord(
        id=str(uuid4()), owner_id=owner.id, name="resolver", source="upload",
        revision_kind="upload", revision_value=REVISION, local_path="/x", status="completed", file_tree=[],
    )
    session.add(repository)
    session.commit()
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", REVISION),
        producer_version_set=producer_version_set or [f"{SOURCE_PRODUCER}@{SOURCE_VERSION}", RESOLVER_PRODUCER],
    )
    return store, snapshot


def _evidence(path: str, line: int = 1) -> Evidence:
    return Evidence(
        path=path, start_line=line, end_line=line,
        extractor=SOURCE_PRODUCER, extractor_version=SOURCE_VERSION,
        logical_line_count=30,
    )


def _node(store, snapshot, kind: str, key: str, *, name: str | None = None, path: str = "src/source.ts", line: int = 1):
    return store.add_node(
        snapshot, node_kind=kind, stable_key=key, name=name, evidence=[_evidence(path, line)]
    )


def _observation(store, snapshot, *, kind: str, subject_kind: str, subject: str, referent: str | None, path: str, line: int):
    return store.add_observation(
        snapshot, observed_kind=kind, subject_kind=subject_kind, subject_key=subject,
        referent_text=referent, ordinal=1, evidence=_evidence(path, line),
    )


def _edge_triples(session, snapshot):
    return {
        (edge.subject_key, edge.predicate, edge.object_key)
        for edge in session.scalars(select(RiEdge).where(RiEdge.snapshot_id == snapshot.snapshot_id))
    }


def test_resolver_persists_all_supported_relationship_kinds(session):
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "module", "mod:src", path="src/source.ts")
    _node(store, snapshot, "file", "file:src/source.ts")
    _node(store, snapshot, "file", "file:src/target.ts", path="src/target.ts")
    caller = _node(store, snapshot, "symbol", "src/source.ts::caller", name="caller", line=2)
    callee = _node(store, snapshot, "symbol", "src/target.ts::callee", name="callee", path="src/target.ts", line=2)
    interface = _node(store, snapshot, "symbol", "src/target.ts::Worker", name="Worker", path="src/target.ts", line=4)
    implementation = _node(store, snapshot, "symbol", "src/source.ts::Runner", name="Runner", line=7)
    route = _node(store, snapshot, "symbol", "src/source.ts::(anonymous:route#1)", name="route", line=12)
    dependency = _node(store, snapshot, "dependency", "dep:npm:react", name="react", path="package.json", line=2)

    _observation(store, snapshot, kind="definition", subject_kind="symbol", subject=caller.stable_key, referent=None, path="src/source.ts", line=2)
    _observation(store, snapshot, kind="definition", subject_kind="symbol", subject=callee.stable_key, referent=None, path="src/target.ts", line=2)
    _observation(store, snapshot, kind="definition", subject_kind="symbol", subject=interface.stable_key, referent=None, path="src/target.ts", line=4)
    _observation(store, snapshot, kind="definition", subject_kind="symbol", subject=implementation.stable_key, referent=None, path="src/source.ts", line=7)
    _observation(store, snapshot, kind="import", subject_kind="file", subject="file:src/source.ts", referent="./target", path="src/source.ts", line=1)
    _observation(store, snapshot, kind="call", subject_kind="symbol", subject=caller.stable_key, referent=callee.stable_key, path="src/source.ts", line=3)
    _observation(store, snapshot, kind="implements", subject_kind="symbol", subject=implementation.stable_key, referent=interface.stable_key, path="src/source.ts", line=7)
    _observation(store, snapshot, kind="route", subject_kind="symbol", subject=route.stable_key, referent="/work", path="src/source.ts", line=12)
    _observation(store, snapshot, kind="route_handler", subject_kind="symbol", subject=route.stable_key, referent=caller.stable_key, path="src/source.ts", line=12)
    _observation(store, snapshot, kind="dependency", subject_kind="dependency", subject=dependency.stable_key, referent="react", path="package.json", line=2)

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.diagnostics_added == 0
    assert result.edges_added == 13
    assert _edge_triples(session, snapshot) == {
        ("file:src/source.ts", "contains", caller.stable_key),
        ("file:src/source.ts", "defines", caller.stable_key),
        ("file:src/target.ts", "contains", callee.stable_key),
        ("file:src/target.ts", "defines", callee.stable_key),
        ("file:src/target.ts", "contains", interface.stable_key),
        ("file:src/target.ts", "defines", interface.stable_key),
        ("file:src/source.ts", "contains", implementation.stable_key),
        ("file:src/source.ts", "defines", implementation.stable_key),
        ("file:src/source.ts", "imports", "file:src/target.ts"),
        (caller.stable_key, "calls", callee.stable_key),
        (implementation.stable_key, "implements", interface.stable_key),
        (route.stable_key, "routes_to", caller.stable_key),
        ("repo:root", "depends_on", dependency.stable_key),
    }

    # Definitions yield two structural edges, so the end-to-end count above is
    # deliberately checked through the stable triples instead of row order.
    assert store.seal(snapshot).state == "completed"


def test_ambiguous_reference_is_a_warning_without_a_guessed_edge(session):
    # A single import binding whose module layout resolves to two files (a real
    # `shared.ts` and `shared.tsx`) is genuine, binding-backed ambiguity — the
    # only way a name reaches more than one candidate now that repository-wide
    # same-name fallback is gone.
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "file", "file:src/source.ts")
    _node(store, snapshot, "file", "file:src/shared.ts", path="src/shared.ts")
    _node(store, snapshot, "file", "file:src/shared.tsx", path="src/shared.tsx")
    caller = _node(store, snapshot, "symbol", "src/source.ts::caller", name="caller", line=2)
    _node(store, snapshot, "symbol", "src/shared.ts::shared", name="shared", path="src/shared.ts")
    _node(store, snapshot, "symbol", "src/shared.tsx::shared", name="shared", path="src/shared.tsx")
    _observation(store, snapshot, kind="import_binding", subject_kind="file", subject="file:src/source.ts", referent="./shared|shared|shared", path="src/source.ts", line=1)
    _observation(store, snapshot, kind="call", subject_kind="symbol", subject=caller.stable_key, referent="shared", path="src/source.ts", line=3)

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    diagnostic = session.scalar(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    assert diagnostic is not None
    assert diagnostic.code == "RI-RES-AMBIGUOUS"
    assert diagnostic.details == {
        "observation_id": diagnostic.details["observation_id"],
        "candidates": ["src/shared.ts::shared", "src/shared.tsx::shared"],
    }
    assert _edge_triples(session, snapshot) == set()
    assert store.seal(snapshot).state == "completed"


def test_call_without_binding_does_not_borrow_a_repository_wide_name(session):
    # One same-named symbol exists in another file, but nothing binds it here.
    # A unique repository-wide name is not proof, so the call stays unresolved.
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "file", "file:src/source.ts")
    caller = _node(store, snapshot, "symbol", "src/source.ts::caller", name="caller", line=2)
    _node(store, snapshot, "symbol", "src/other.ts::helper", name="helper", path="src/other.ts")
    _observation(store, snapshot, kind="call", subject_kind="symbol", subject=caller.stable_key, referent="helper", path="src/source.ts", line=3)

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    diagnostic = session.scalar(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    assert diagnostic is not None and diagnostic.code == "RI-RES-UNRESOLVED"
    assert not [edge for edge in _edge_triples(session, snapshot) if edge[1] == "calls"]
    assert store.seal(snapshot).state == "completed"


def test_broken_binding_does_not_fall_back_to_a_same_named_symbol(session):
    # The binding names a module that resolves to no file node. Even with an
    # unrelated `run` defined elsewhere, a failed binding stays unresolved
    # rather than borrowing that symbol.
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "file", "file:src/source.ts")
    caller = _node(store, snapshot, "symbol", "src/source.ts::caller", name="caller", line=2)
    _node(store, snapshot, "symbol", "src/other.ts::run", name="run", path="src/other.ts")
    _observation(store, snapshot, kind="import_binding", subject_kind="file", subject="file:src/source.ts", referent="./missing|run|run", path="src/source.ts", line=1)
    _observation(store, snapshot, kind="call", subject_kind="symbol", subject=caller.stable_key, referent="run", path="src/source.ts", line=3)

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    codes = {
        diagnostic.code
        for diagnostic in session.scalars(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    }
    assert codes == {"RI-RES-UNRESOLVED"}
    assert not [edge for edge in _edge_triples(session, snapshot) if edge[1] == "calls"]
    assert store.seal(snapshot).state == "completed"


def test_imported_route_handler_without_resolvable_binding_stays_unresolved(session):
    # routes_to follows the same no-fallback rule as calls/implements: a handler
    # referent whose binding does not resolve is unresolved, never matched to an
    # unrelated same-named component elsewhere.
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "file", "file:src/routes.ts", path="src/routes.ts")
    route = _node(store, snapshot, "symbol", "src/routes.ts::(anonymous:route#1)", name="route", path="src/routes.ts", line=2)
    _node(store, snapshot, "symbol", "src/other.ts::Handler", name="Handler", path="src/other.ts")
    _observation(store, snapshot, kind="route", subject_kind="symbol", subject=route.stable_key, referent="/x", path="src/routes.ts", line=2)
    _observation(store, snapshot, kind="route_handler", subject_kind="symbol", subject=route.stable_key, referent="Handler", path="src/routes.ts", line=2)
    _observation(store, snapshot, kind="import_binding", subject_kind="file", subject="file:src/routes.ts", referent="./missing|Handler|Handler", path="src/routes.ts", line=1)

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    assert not [edge for edge in _edge_triples(session, snapshot) if edge[1] == "routes_to"]
    codes = {
        diagnostic.code
        for diagnostic in session.scalars(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    }
    assert codes == {"RI-RES-UNRESOLVED"}
    assert store.seal(snapshot).state == "completed"


def test_implemented_interface_without_evidence_stays_unresolved(session):
    # `implements Contract` with no same-file definition and no import binding is
    # unresolved even though exactly one `Contract` exists elsewhere.
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "file", "file:src/impl.ts", path="src/impl.ts")
    impl = _node(store, snapshot, "symbol", "src/impl.ts::Service", name="Service", path="src/impl.ts", line=2)
    _node(store, snapshot, "symbol", "src/other.ts::Contract", name="Contract", path="src/other.ts")
    _observation(store, snapshot, kind="implements", subject_kind="symbol", subject=impl.stable_key, referent="Contract", path="src/impl.ts", line=2)

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    assert not [edge for edge in _edge_triples(session, snapshot) if edge[1] == "implements"]
    diagnostic = session.scalar(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    assert diagnostic is not None and diagnostic.code == "RI-RES-UNRESOLVED"
    assert store.seal(snapshot).state == "completed"


def test_unresolved_import_is_preserved_as_a_warning(session):
    store, snapshot = _store(session)
    _node(store, snapshot, "repository", "repo:root")
    _node(store, snapshot, "file", "file:src/source.ts")
    _observation(store, snapshot, kind="import", subject_kind="file", subject="file:src/source.ts", referent="./missing", path="src/source.ts", line=1)

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    diagnostic = session.scalar(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    assert diagnostic is not None and diagnostic.code == "RI-RES-UNRESOLVED"
    assert diagnostic.details["observation_id"].startswith("obs:sha256:")
    assert store.seal(snapshot).state == "completed"


def _persist_extraction(store, snapshot, result, producer: str):
    for node in result.nodes:
        store.add_node(
            snapshot,
            node_kind=node.node_kind,
            stable_key=node.stable_key,
            name=node.name,
            language=node.language,
            properties=node.properties,
            ordered_array_keys=frozenset({"decorators"}) if node.properties and "decorators" in node.properties else frozenset(),
            evidence=[
                Evidence(
                    path=evidence.path,
                    start_line=evidence.start_line,
                    end_line=evidence.end_line,
                    extractor=producer,
                    extractor_version="1.0.0",
                    logical_line_count=evidence.logical_line_count,
                    granularity=evidence.granularity,
                )
                for evidence in node.evidence
            ],
        )
    for observation in result.observations:
        store.add_observation(
            snapshot,
            observed_kind=observation.observed_kind,
            subject_kind=observation.subject_kind,
            subject_key=observation.subject_key,
            referent_text=observation.referent_text,
            ordinal=observation.ordinal,
            evidence=Evidence(
                path=observation.evidence.path,
                start_line=observation.evidence.start_line,
                end_line=observation.evidence.end_line,
                extractor=producer,
                extractor_version="1.0.0",
                logical_line_count=observation.evidence.logical_line_count,
                granularity=observation.evidence.granularity,
            ),
        )


def test_typescript_extractor_inputs_resolve_import_and_aliased_call(session):
    store, snapshot = _store(session, ["typescript-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("src/source.ts", 1, 1, "typescript-ast", "1.0.0", 3)
    ])
    extractor = TypeScriptExtractor()
    _persist_extraction(
        store,
        snapshot,
        extractor.extract("src/target.ts", b"export function target() { return 1; }\n"),
        "typescript-ast",
    )
    _persist_extraction(
        store,
        snapshot,
        extractor.extract(
            "src/source.ts",
            b"import { target as invoke } from './target';\nexport function caller() { return invoke(); }\n",
        ),
        "typescript-ast",
    )

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.diagnostics_added == 0
    assert ("file:src/source.ts", "imports", "file:src/target.ts") in _edge_triples(session, snapshot)
    assert ("src/source.ts::caller", "calls", "src/target.ts::target") in _edge_triples(session, snapshot)
    assert store.seal(snapshot).state == "completed"


def test_python_extractor_route_inputs_resolve_to_the_decorated_handler(session):
    store, snapshot = _store(session, ["python-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("app/routes.py", 1, 1, "python-ast", "1.0.0", 3)
    ])
    store.add_node(snapshot, node_kind="file", stable_key="file:app/routes.py", evidence=[
        Evidence("app/routes.py", 1, 3, "python-ast", "1.0.0", 3, "file")
    ])
    _persist_extraction(
        store,
        snapshot,
        PythonExtractor().extract(
            "app/routes.py", b"@router.get('/health')\ndef health():\n    return None\n"
        ),
        "python-ast",
    )

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.diagnostics_added == 0
    assert (
        "app/routes.py::(anonymous:route#1)",
        "routes_to",
        "app/routes.py::health",
    ) in _edge_triples(session, snapshot)
    assert store.seal(snapshot).state == "completed"


def test_golden_ambiguous_call_fixture_emits_a_diagnostic_not_an_edge(session):
    # The fixture calls `shared()` with no import binding while two files export
    # a `shared` symbol. Without lexical or import evidence the resolver proves
    # nothing, so the honest outcome is a single unresolved diagnostic and no
    # `calls` edge — never a guess at one of the same-named repository symbols.
    fixture = FIXTURE_ROOT / "ambiguous-call"
    store, snapshot = _store(session, ["typescript-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("src/source.ts", 1, 1, "typescript-ast", "1.0.0", 3)
    ])
    extractor = TypeScriptExtractor()
    for source_path in sorted(fixture.rglob("*.ts")):
        relative = source_path.relative_to(fixture).as_posix()
        _persist_extraction(store, snapshot, extractor.extract(relative, source_path.read_bytes()), "typescript-ast")

    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 6  # three definitions, each with contains + defines
    diagnostics = list(session.scalars(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id)))
    assert [diagnostic.code for diagnostic in diagnostics] == ["RI-RES-UNRESOLVED"]
    assert not [edge for edge in _edge_triples(session, snapshot) if edge[1] == "calls"]
    assert store.seal(snapshot).state == "completed"


def _python_import_snapshot(session, source: bytes, *, files: list[str], dependencies: list[str] = ()):
    """Persist a single Python source plus explicit file/dependency nodes.

    File nodes stand in for the inventory extractor that runs alongside the
    Python extractor in production; the resolver reads only stored nodes.
    """

    store, snapshot = _store(session, ["python-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("app/main.py", 1, 1, "python-ast", "1.0.0", 3)
    ])
    for path in files:
        store.add_node(snapshot, node_kind="file", stable_key=f"file:{path}", evidence=[
            Evidence(path, 1, 1, "python-ast", "1.0.0", 1, "file")
        ])
    for name in dependencies:
        store.add_node(snapshot, node_kind="dependency", stable_key=f"dep:pypi:{name}", name=name, evidence=[
            Evidence("pyproject.toml", 1, 1, "python-ast", "1.0.0", 1)
        ])
    _persist_extraction(store, snapshot, PythonExtractor().extract("app/main.py", source), "python-ast")
    return store, snapshot


def test_python_absolute_from_import_resolves_to_the_module_file(session):
    # `from pkg.service import run` is stored as referent `pkg.service.run`; the
    # binding proves the module is `pkg.service`, so the import edge resolves to
    # the module file `pkg/service.py`, not only `pkg/service/run.py`.
    store, snapshot = _python_import_snapshot(
        session, b"from pkg.service import run\n", files=["app/main.py", "pkg/service.py"]
    )
    result = RelationshipResolver(store).resolve(snapshot)
    assert result.diagnostics_added == 0
    assert ("file:app/main.py", "imports", "file:pkg/service.py") in _edge_triples(session, snapshot)
    assert store.seal(snapshot).state == "completed"


def test_python_absolute_from_import_prefers_local_module_over_dependency(session):
    # A `dep:pypi:pkg` node with the same package root must not replace the local
    # module once a local file candidate exists.
    store, snapshot = _python_import_snapshot(
        session, b"from pkg.service import run\n",
        files=["app/main.py", "pkg/service.py"], dependencies=["pkg"],
    )
    result = RelationshipResolver(store).resolve(snapshot)
    assert result.diagnostics_added == 0
    triples = _edge_triples(session, snapshot)
    assert ("file:app/main.py", "imports", "file:pkg/service.py") in triples
    assert ("file:app/main.py", "imports", "dep:pypi:pkg") not in triples
    assert store.seal(snapshot).state == "completed"


def test_python_absolute_from_import_without_module_or_dependency_is_unresolved(session):
    store, snapshot = _python_import_snapshot(
        session, b"from pkg.service import run\n", files=["app/main.py"]
    )
    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    assert not [edge for edge in _edge_triples(session, snapshot) if edge[1] == "imports"]
    diagnostic = session.scalar(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    assert diagnostic is not None and diagnostic.code == "RI-RES-UNRESOLVED"
    assert store.seal(snapshot).state == "completed"


def test_python_absolute_from_import_with_two_module_candidates_is_ambiguous(session):
    # Both interpretations exist as files: `run` as a member of `pkg/service.py`
    # and `run` as the submodule `pkg/service/run.py`. Deterministically ambiguous.
    store, snapshot = _python_import_snapshot(
        session, b"from pkg.service import run\n",
        files=["app/main.py", "pkg/service.py", "pkg/service/run.py"],
    )
    result = RelationshipResolver(store).resolve(snapshot)
    assert result.edges_added == 0
    assert not [edge for edge in _edge_triples(session, snapshot) if edge[1] == "imports"]
    diagnostic = session.scalar(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot.snapshot_id))
    assert diagnostic is not None and diagnostic.code == "RI-RES-AMBIGUOUS"
    assert diagnostic.details["candidates"] == ["file:pkg/service.py", "file:pkg/service/run.py"]
    assert store.seal(snapshot).state == "completed"


def test_shadowed_typescript_parameter_does_not_resolve_to_same_file_global(session):
    store, snapshot = _store(session, ["typescript-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("src/main.ts", 1, 1, "typescript-ast", "1.0.0", 2)
    ])
    _persist_extraction(
        store,
        snapshot,
        TypeScriptExtractor().extract(
            "src/main.ts",
            b"export function target() { return 1; }\n"
            b"export function caller(target: () => number) { return target(); }\n",
        ),
        "typescript-ast",
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.diagnostics_added == 1
    assert (
        "src/main.ts::caller",
        "calls",
        "src/main.ts::target",
    ) not in _edge_triples(session, snapshot)
    diagnostic = session.scalar(
        select(RiDiagnostic).where(
            RiDiagnostic.snapshot_id == snapshot.snapshot_id,
            RiDiagnostic.code == "RI-RES-UNRESOLVED",
        )
    )
    assert diagnostic is not None
    assert diagnostic.message == "calls target is shadowed by a local binding"


def test_shadowed_python_parameter_does_not_resolve_to_same_file_global(session):
    store, snapshot = _store(session, ["python-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("app/main.py", 1, 1, "python-ast", "1.0.0", 4)
    ])
    store.add_node(snapshot, node_kind="file", stable_key="file:app/main.py", evidence=[
        Evidence("app/main.py", 1, 4, "python-ast", "1.0.0", 4, "file")
    ])
    _persist_extraction(
        store,
        snapshot,
        PythonExtractor().extract(
            "app/main.py",
            b"def target():\n    return 1\n"
            b"def caller(target):\n    return target()\n",
        ),
        "python-ast",
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.diagnostics_added == 1
    assert (
        "app/main.py::caller",
        "calls",
        "app/main.py::target",
    ) not in _edge_triples(session, snapshot)


def test_default_imported_react_route_handler_resolves(session):
    store, snapshot = _store(session, ["typescript-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("src/routes.tsx", 1, 1, "typescript-ast", "1.0.0", 2)
    ])
    extractor = TypeScriptExtractor()
    _persist_extraction(
        store,
        snapshot,
        extractor.extract(
            "src/Home.tsx",
            b"const Home = () => null;\nexport default Home;\n",
        ),
        "typescript-ast",
    )
    _persist_extraction(
        store,
        snapshot,
        extractor.extract(
            "src/routes.tsx",
            b"import Home from './Home';\n"
            b"const routes = createBrowserRouter([{ path: '/', Component: Home }]);\n",
        ),
        "typescript-ast",
    )

    RelationshipResolver(store).resolve(snapshot)

    assert (
        "src/routes.tsx::(anonymous:route#1)",
        "routes_to",
        "src/Home.tsx::Home",
    ) in _edge_triples(session, snapshot)


def test_top_level_and_recursive_calls_resolve_without_dropping_self_edges(session):
    store, snapshot = _store(session, ["typescript-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("src/main.ts", 1, 1, "typescript-ast", "1.0.0", 4)
    ])
    _persist_extraction(
        store,
        snapshot,
        TypeScriptExtractor().extract(
            "src/main.ts",
            b"export function recurse(value: number): number {\n"
            b"  return value > 0 ? recurse(value - 1) : value;\n"
            b"}\n"
            b"recurse(2);\n",
        ),
        "typescript-ast",
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.diagnostics_added == 0
    triples = _edge_triples(session, snapshot)
    assert (
        "src/main.ts::recurse",
        "calls",
        "src/main.ts::recurse",
    ) in triples
    assert (
        "file:src/main.ts",
        "calls",
        "src/main.ts::recurse",
    ) in triples


def test_abstract_generic_implements_resolves_to_base_interface(session):
    store, snapshot = _store(session, ["typescript-ast@1.0.0", RESOLVER_PRODUCER])
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[
        Evidence("src/worker.ts", 1, 1, "typescript-ast", "1.0.0", 2)
    ])
    _persist_extraction(
        store,
        snapshot,
        TypeScriptExtractor().extract(
            "src/worker.ts",
            b"export interface Worker<T> { run(value: T): void; }\n"
            b"export abstract class Runner implements Worker<string> { abstract run(value: string): void; }\n",
        ),
        "typescript-ast",
    )

    result = RelationshipResolver(store).resolve(snapshot)

    assert result.diagnostics_added == 0
    assert (
        "src/worker.ts::Runner",
        "implements",
        "src/worker.ts::Worker",
    ) in _edge_triples(session, snapshot)


def test_python_relative_import_still_resolves_to_the_sibling_module(session):
    store, snapshot = _python_import_snapshot(
        session, b"from .service import run\n", files=["app/main.py", "app/service.py"]
    )
    result = RelationshipResolver(store).resolve(snapshot)
    assert result.diagnostics_added == 0
    assert ("file:app/main.py", "imports", "file:app/service.py") in _edge_triples(session, snapshot)
    assert store.seal(snapshot).state == "completed"
