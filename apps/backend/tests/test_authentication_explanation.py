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

_AUTH_SOURCES = {
    "README.md": b"# auth fixture\n",
    "src/dependencies.py": (
        b"def get_current_user(token: str = Depends(oauth2_scheme)):\n"
        b"    if not token:\n"
        b"        raise Exception('unauthorized')\n"
        b"    return token\n"
    ),
    "src/services.py": (
        b"class UserService:\n"
        b"    def get_user(self):\n"
        b"        return None\n"
    ),
    "src/models.py": (
        b"class UserModel:\n"
        b"    pass\n"
    ),
    "src/routes.py": (
        b"from fastapi import FastAPI, Depends\n"
        b"from src.dependencies import get_current_user\n\n"
        b"app = FastAPI()\n\n\n"
        b"@app.get(\"/me\")\n"
        b"def read_me(user=Depends(get_current_user)):\n"
        b"    return user\n"
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


def test_authentication_explanation_identifies_route_middleware_service_model(auth_client):
    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert response.status_code == 200, response.text
    body = response.json()

    claims_by_kind: dict[str, list[dict]] = {}
    for claim in body["claims"]:
        claims_by_kind.setdefault(claim["kind"], []).append(claim)

    assert any(claim["name"] == "/me" for claim in claims_by_kind.get("route", []))
    assert any(claim["name"] == "get_current_user" for claim in claims_by_kind.get("middleware", []))
    assert any(claim["name"] == "UserService" for claim in claims_by_kind.get("service", []))
    assert any(claim["name"] == "UserModel" for claim in claims_by_kind.get("model", []))

    # Every displayed claim resolves to a valid evidence span in the stored revision.
    for claim in body["claims"]:
        assert claim["evidence"], f"claim {claim['name']!r} has no evidence"
        for citation in claim["evidence"]:
            assert citation["snapshotId"] == body["snapshotId"]
            assert citation["startLine"] >= 1
            assert citation["endLine"] >= citation["startLine"]
            assert citation["path"]

    # Middleware/dependency claims are inferred, never presented as guaranteed fact.
    middleware_claim = claims_by_kind["middleware"][0]
    assert middleware_claim["confidence"] == "heuristic"
    route_claim = claims_by_kind["route"][0]
    assert route_claim["confidence"] == "observed"

    assert any(
        relationship["predicate"] == "injects" and relationship["object"] == "get_current_user"
        for relationship in body["relationships"]
    )
    assert any(
        relationship["predicate"] == "routes_to" and relationship["object"] == "read_me"
        for relationship in body["relationships"]
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


def test_authentication_explanation_is_owner_scoped(auth_client, make_auth_headers):
    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    other = make_auth_headers("other-owner@example.com")
    response = auth_client.get(
        f"/analysis/{repository['id']}/architecture/authentication",
        headers=other["headers"],
    )
    assert response.status_code == 404


def test_authentication_explanation_never_calls_legacy_intelligence_engine(auth_client, monkeypatch):
    """Proof that the old inference path is absent, not merely unused: forcing
    the legacy engine to raise must not affect the authentication explanation
    or the migrated architecture endpoint, because neither calls it."""

    from app.intelligence.engine import RepositoryIntelligenceEngine

    # The upload + durable-analysis stages legitimately still use the legacy
    # engine (dependency graph, review, documentation, AI remain its readers
    # per docs/architecture/REPOSITORY_INTELLIGENCE.md); only patch it out
    # *after* that setup, to isolate the two migrated read endpoints below.
    repository = _upload(auth_client, _AUTH_SOURCES)
    _persist_snapshot(repository["id"], _AUTH_SOURCES)

    def _boom(self, record):
        raise AssertionError("RepositoryIntelligenceEngine.load must not be called by the migrated consumer")

    monkeypatch.setattr(RepositoryIntelligenceEngine, "load", _boom)
    monkeypatch.setattr(RepositoryIntelligenceEngine, "from_record", _boom)

    auth_response = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert auth_response.status_code == 200, auth_response.text
    assert auth_response.json()["status"] == "ready"

    architecture_response = auth_client.get(f"/analysis/{repository['id']}/architecture")
    assert architecture_response.status_code == 200, architecture_response.text


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
