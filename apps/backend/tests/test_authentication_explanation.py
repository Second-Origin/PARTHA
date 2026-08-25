from __future__ import annotations

import shutil

from app.extraction.manifests import DependencyManifestExtractor
from app.extraction.pipeline import ExtractionPipeline
from app.extraction.python import PythonExtractor
from app.intelligence.classification import RoleClassifier
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models.repository import RepositoryRecord

from tests.analysis_helpers import run_analysis_jobs

# A genuinely connected authentication path (route -> handler -> guard ->
# service -> model, every hop a resolved edge) alongside unrelated noise that
# must never be claimed as authentication: an unrelated `/health` route, a
# generic `Depends(get_database)`, and disconnected `PaymentService` /
# `AuditModel` symbols that merely share a role-classifier suffix.
_AUTH_SOURCES = {
    "README.md": b"# auth fixture\n",
    "src/dependencies.py": (
        b"from src.services import UserService\n\n\n"
        b"def get_current_user(token: str) -> dict:\n"
        b"    return UserService(token)\n\n\n"
        b"def get_database() -> str:\n"
        b"    return 'db-session'\n"
    ),
    "src/services.py": (
        b"from src.models import UserModel\n\n\n"
        b"def UserService(token: str) -> dict:\n"
        b"    return UserModel(token)\n\n\n"
        b"def PaymentService(amount: int) -> int:\n"
        b"    return amount\n"
    ),
    "src/models.py": (
        b"def UserModel(token: str) -> dict:\n"
        b"    return {'token': token}\n\n\n"
        b"def AuditModel(event: str) -> dict:\n"
        b"    return {'event': event}\n"
    ),
    "src/routes.py": (
        b"from fastapi import FastAPI, Depends\n"
        b"from src.dependencies import get_current_user, get_database\n\n"
        b"app = FastAPI()\n\n\n"
        b"@app.get(\"/me\")\n"
        b"def read_me(user=Depends(get_current_user)):\n"
        b"    return user\n\n\n"
        b"@app.get(\"/health\")\n"
        b"def health_check(db=Depends(get_database)):\n"
        b"    return {'status': 'ok'}\n"
    ),
}


def _upload(auth_client, files: dict[str, bytes], *, analyse: bool = True) -> dict:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("auth.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
    if analyse:
        assert run_analysis_jobs() == 1
    return repository


def _evidence(item, extractor: str, version: str) -> Evidence:
    return Evidence(
        path=item.path,
        start_line=item.start_line,
        end_line=item.end_line,
        extractor=extractor,
        extractor_version=version,
        logical_line_count=item.logical_line_count,
        granularity=item.granularity,
    )


def _persist_snapshot(repository_id: str, sources: dict[str, bytes]) -> str:
    from app.core.database import SessionLocal

    pipeline = ExtractionPipeline([PythonExtractor(), DependencyManifestExtractor()])
    runs = pipeline.run(sources)
    producer_version_set = sorted(
        {run.producer for run in runs}
        | {f"{RelationshipResolver.name}@{RelationshipResolver.version}", f"{RoleClassifier.name}@{RoleClassifier.version}"}
    )

    with SessionLocal() as session:
        repository = session.get(RepositoryRecord, repository_id)
        assert repository is not None
        store = SnapshotStore(session)
        snapshot = store.begin(
            repository_id=repository.id,
            revision=Revision(repository.revision_kind, repository.revision_value, repository.revision_ref),
            producer_version_set=producer_version_set,
        )
        for run in runs:
            for node in run.result.nodes:
                store.add_node(
                    snapshot,
                    node_kind=node.node_kind,
                    stable_key=node.stable_key,
                    name=node.name,
                    language=node.language,
                    properties=node.properties,
                    set_array_keys=(
                        frozenset({"decorators"})
                        if node.properties and "decorators" in node.properties
                        else frozenset()
                    ),
                    evidence=[_evidence(item, run.producer_name, run.producer_version) for item in node.evidence],
                )
            for observation in run.result.observations:
                store.add_observation(
                    snapshot,
                    observed_kind=observation.observed_kind,
                    subject_kind=observation.subject_kind,
                    subject_key=observation.subject_key,
                    referent_text=observation.referent_text,
                    ordinal=observation.ordinal,
                    evidence=_evidence(observation.evidence, run.producer_name, run.producer_version),
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
        RelationshipResolver(store).resolve(snapshot)
        RoleClassifier(store).classify(snapshot)
        return store.seal(snapshot).snapshot_id


def test_authentication_explanation_survives_filesystem_deletion(auth_client):
    """The consumer performs no filesystem read: proof #2 of the acceptance
    criteria. Deleting the extracted working directory must not affect the
    response, because it is built exclusively from persisted snapshot facts."""

    repository = _upload(auth_client, _AUTH_SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _AUTH_SOURCES)

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        local_path = record.local_path
    shutil.rmtree(local_path)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["snapshotId"] == snapshot_id


def test_authentication_explanation_includes_the_connected_path(auth_client):
    """The real route -> handler -> guard -> service -> model chain is
    included, and every claim/relationship carries valid evidence."""

    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200, response.text
    body = response.json()

    claims_by_kind: dict[str, list[dict]] = {}
    for claim in body["claims"]:
        claims_by_kind.setdefault(claim["kind"], []).append(claim)

    assert {claim["name"] for claim in claims_by_kind.get("route", [])} == {"/me"}
    assert {claim["name"] for claim in claims_by_kind.get("middleware", [])} == {"get_current_user"}
    assert {claim["name"] for claim in claims_by_kind.get("service", [])} == {"UserService"}
    assert {claim["name"] for claim in claims_by_kind.get("model", [])} == {"UserModel"}

    # Every displayed claim resolves to a valid evidence span in the stored revision.
    for claim in body["claims"]:
        assert claim["evidence"], f"claim {claim['name']!r} has no evidence"
        for citation in claim["evidence"]:
            assert citation["snapshotId"] == body["snapshotId"]
            assert citation["startLine"] >= 1
            assert citation["endLine"] >= citation["startLine"]
            assert citation["path"]

    # Middleware/service/model claims are inferred, never presented as guaranteed fact.
    middleware_claim = claims_by_kind["middleware"][0]
    assert middleware_claim["confidence"] == "heuristic"
    route_claim = claims_by_kind["route"][0]
    assert route_claim["confidence"] == "observed"

    relationship_pairs = {(r["subject"], r["predicate"], r["object"]) for r in body["relationships"]}
    assert ("/me", "routes_to", "read_me") in relationship_pairs
    assert ("read_me", "injects", "get_current_user") in relationship_pairs
    assert ("get_current_user", "calls", "UserService") in relationship_pairs
    assert ("UserService", "calls", "UserModel") in relationship_pairs
    for relationship in body["relationships"]:
        assert relationship["evidence"]

    assert len(body["chains"]) == 1
    chain = body["chains"][0]
    assert chain["route"] == "/me"
    assert [hop["predicate"] for hop in chain["hops"]] == ["routes_to", "injects", "calls", "calls"]


def test_authentication_explanation_keeps_shared_hops_in_every_chain(auth_client):
    """Two guarded routes may converge on the same guard/service/model path.

    The flat relationship list is de-duplicated, but each per-route chain must
    still contain the complete shared path.
    """

    sources = {
        **_AUTH_SOURCES,
        "src/routes.py": (
            b"from fastapi import FastAPI, Depends\n"
            b"from src.dependencies import get_current_user\n\n"
            b"app = FastAPI()\n\n\n"
            b"@app.get(\"/me\")\n"
            b"def read_me(user=Depends(get_current_user)):\n"
            b"    return user\n\n\n"
            b"@app.get(\"/account\")\n"
            b"def read_account(user=Depends(get_current_user)):\n"
            b"    return user\n"
        ),
    }
    repository = _upload(auth_client, sources)
    _persist_snapshot(repository["id"], sources)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200, response.text
    body = response.json()

    chains_by_route = {chain["route"]: chain for chain in body["chains"]}
    assert set(chains_by_route) == {"/me", "/account"}
    for chain in chains_by_route.values():
        assert [hop["predicate"] for hop in chain["hops"]] == [
            "routes_to",
            "injects",
            "calls",
            "calls",
        ]

    relationship_keys = [
        (item["subject"], item["predicate"], item["object"])
        for item in body["relationships"]
    ]
    assert relationship_keys.count(("get_current_user", "calls", "UserService")) == 1
    assert relationship_keys.count(("UserService", "calls", "UserModel")) == 1


def test_authentication_explanation_excludes_unrelated_route_and_dependency(auth_client):
    """`/health` and its generic `Depends(get_database)` are never authentication."""

    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200, response.text
    body = response.json()

    names = {claim["name"] for claim in body["claims"]}
    assert "/health" not in names
    assert "get_database" not in names
    assert "health_check" not in names

    for relationship in body["relationships"]:
        assert relationship["subject"] not in {"/health", "get_database", "health_check"}
        assert relationship["object"] not in {"/health", "get_database", "health_check"}


def test_authentication_explanation_excludes_unrelated_service_and_model(auth_client):
    """`PaymentService`/`AuditModel` share a role-classifier suffix with the
    real auth path but are never called from it, so they must not appear."""

    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200, response.text
    body = response.json()

    names = {claim["name"] for claim in body["claims"]}
    assert "PaymentService" not in names
    assert "AuditModel" not in names

    for relationship in body["relationships"]:
        assert relationship["subject"] not in {"PaymentService", "AuditModel"}
        assert relationship["object"] not in {"PaymentService", "AuditModel"}


def test_authentication_explanation_excludes_public_route_without_a_guard(auth_client):
    """A route whose only dependency is non-authentication is not claimed,
    even though it is a perfectly resolved `injects` edge."""

    sources = {
        "src/dependencies.py": b"def get_database() -> str:\n    return 'db-session'\n",
        "src/routes.py": (
            b"from fastapi import FastAPI, Depends\n"
            b"from src.dependencies import get_database\n\n"
            b"app = FastAPI()\n\n\n"
            b"@app.get(\"/health\")\n"
            b"def health_check(db=Depends(get_database)):\n"
            b"    return {'status': 'ok'}\n"
        ),
    }
    repository = _upload(auth_client, sources)
    _persist_snapshot(repository["id"], sources)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200
    body = response.json()
    assert body["claims"] == []
    assert body["relationships"] == []
    assert body["chains"] == []
    # get_database resolves fine as an `injects` edge -- it just is not
    # classified `auth_dependency`, so nothing surfaces. This is a "filtered
    # out" empty result, not an extraction failure: prove the edge is real.
    from app.core.database import SessionLocal
    from app.intelligence.query_service import SnapshotQueryService

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        query_service = SnapshotQueryService(session, record.owner_id)
        facts = query_service.architecture_facts(record.id)
        assert facts is not None
        assert any(
            edge.predicate == "injects" and edge.object_key.endswith("get_database")
            for edge in facts.edges
        )


def test_authentication_explanation_missing_snapshot_is_honest(auth_client):
    """A repository with no sealed snapshot yet reports status=missing_snapshot,
    distinguishable from a genuinely empty (analysed, zero-claim) result."""

    repository = _upload(auth_client, {"README.md": b"# empty\n"}, analyse=False)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_snapshot"
    assert body["snapshotId"] is None
    assert body["claims"] == []
    assert any(diagnostic["code"] == "AUTH-NO-SNAPSHOT" for diagnostic in body["diagnostics"])


def test_authentication_explanation_no_auth_is_distinguishable_from_unparsed(auth_client):
    """A repository with genuinely no auth constructs returns zero claims and
    no diagnostics: absence is not confused with an unsupported construct."""

    sources = {"src/plain.py": b"def add(a, b):\n    return a + b\n"}
    repository = _upload(auth_client, sources)
    _persist_snapshot(repository["id"], sources)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["claims"] == []
    assert body["relationships"] == []
    assert body["chains"] == []
    assert body["diagnostics"] == []


def test_authentication_explanation_unresolved_dependency_is_a_visible_diagnostic(auth_client):
    """A ``Depends(x)`` whose target cannot be resolved (undefined/ambiguous)
    surfaces as a visible diagnostic rather than being silently dropped."""

    sources = {
        "src/routes.py": (
            b"from fastapi import FastAPI, Depends\n\n"
            b"app = FastAPI()\n\n\n"
            b"@app.get(\"/me\")\n"
            b"def read_me(user=Depends(get_current_user)):\n"
            b"    return user\n"
        ),
    }
    repository = _upload(auth_client, sources)
    _persist_snapshot(repository["id"], sources)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200
    body = response.json()
    assert any(diagnostic["code"] == "RI-RES-UNRESOLVED" for diagnostic in body["diagnostics"])
    assert body["claims"] == []


def test_authentication_explanation_is_owner_scoped(auth_client, make_auth_headers):
    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    other = make_auth_headers("other-owner@example.com")
    response = auth_client.get(
        f"/analysis/{repository['id']}/architecture/authentication",
        headers=other["headers"],
    )
    assert response.status_code == 404


def test_authentication_explanation_evidence_binds_to_exact_snapshot(auth_client):
    """Re-persisting a new snapshot for the same repository must not let an old
    snapshot's facts leak into the current explanation (#95 wrong-revision
    rejection): every citation names the current snapshot only."""

    repository = _upload(auth_client, _AUTH_SOURCES)
    first_snapshot_id = _persist_snapshot(repository["id"], _AUTH_SOURCES)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    body = response.json()
    assert body["snapshotId"] == first_snapshot_id
    for claim in body["claims"]:
        for citation in claim["evidence"]:
            assert citation["snapshotId"] == first_snapshot_id
    for relationship in body["relationships"]:
        for citation in relationship["evidence"]:
            assert citation["snapshotId"] == first_snapshot_id


def test_authentication_explanation_evidence_fact_ids_resolve_to_real_facts(auth_client):
    """Every evidence ``factId`` must name a node or edge that genuinely exists
    in the returned snapshot — not merely a non-empty string."""

    from app.core.database import SessionLocal
    from app.intelligence.query_service import SnapshotQueryService

    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    body = response.json()

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        query_service = SnapshotQueryService(session, record.owner_id)
        facts = query_service.architecture_facts(record.id)
        assert facts is not None
        node_keys = {node.stable_key for node in facts.nodes}
        edge_ids = {edge.edge_id for edge in facts.edges}
        source_paths = {
            evidence_item.path
            for evidence_list in facts.node_evidence.values()
            for evidence_item in evidence_list
        } | {
            evidence_item.path
            for evidence_list in facts.edge_evidence.values()
            for evidence_item in evidence_list
        }

    for claim in body["claims"]:
        for citation in claim["evidence"]:
            assert citation["factId"] in node_keys
            assert citation["path"] in source_paths
    for relationship in body["relationships"]:
        for citation in relationship["evidence"]:
            assert citation["factId"] in edge_ids
            assert citation["path"] in source_paths


# A real, connected auth chain in production source alongside a structurally
# identical one whose every file lives under tests/ -- reproducing the
# 2026-08-20 audit finding that a benchmark test fixture was picked as "the"
# authentication flow for PARTHA's own repository (#337).
_AUTH_SOURCES_WITH_TEST_FIXTURE = {
    **_AUTH_SOURCES,
    "tests/fixtures/dependencies.py": (
        b"from tests.fixtures.services import UserService\n\n\n"
        b"def get_current_user(token: str) -> dict:\n"
        b"    return UserService(token)\n"
    ),
    "tests/fixtures/services.py": (
        b"def UserService(token: str) -> dict:\n"
        b"    return {'token': token}\n"
    ),
    "tests/fixtures/routes.py": (
        b"from fastapi import FastAPI, Depends\n"
        b"from tests.fixtures.dependencies import get_current_user\n\n"
        b"app = FastAPI()\n\n\n"
        b"@app.get(\"/me\")\n"
        b"def read_me(user=Depends(get_current_user)):\n"
        b"    return user\n"
    ),
}


def test_authentication_explanation_excludes_test_fixture_routes(auth_client):
    """A route defined only in a test/fixture path must never be claimed as
    this repository's authentication flow, even when it is itself a
    structurally valid guarded route (#337)."""

    repository = _upload(auth_client, _AUTH_SOURCES_WITH_TEST_FIXTURE)
    _persist_snapshot(repository["id"], _AUTH_SOURCES_WITH_TEST_FIXTURE)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200, response.text
    body = response.json()

    for claim in body["claims"]:
        for citation in claim["evidence"]:
            assert not citation["path"].startswith("tests/"), (
                f"claim {claim['name']!r} is backed by a test-fixture path {citation['path']!r}"
            )

    # The real route from src/routes.py is still reported -- this excludes
    # the fixture, it does not suppress genuine findings. Both "/me" routes
    # share the same display name, so the count (not just the name set)
    # is what proves the fixture's duplicate was actually dropped.
    route_claims = [claim for claim in body["claims"] if claim["kind"] == "route"]
    assert len(route_claims) == 1
    assert route_claims[0]["name"] == "/me"
    assert len(body["chains"]) == 1
    assert body["chains"][0]["route"] == "/me"
    assert all(hop["evidence"][0]["path"].startswith("src/") for hop in body["chains"][0]["hops"])
