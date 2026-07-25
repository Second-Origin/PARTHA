"""Public Engineering Review v2 contract and provenance tests (#154)."""

from __future__ import annotations

import io
import zipfile

from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models.repository import RepositoryRecord

from tests.analysis_helpers import run_analysis_jobs

_FINDING_SOURCES = {
    "README.md": b"# review fixture\n",
    "src/index.ts": (
        b"import { missing } from './missing';\n"
        b"export const value = missing();\n"
    ),
}
_EMPTY_SOURCES = {
    "README.md": b"# review fixture with no supported diagnostics\n",
}


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload(auth_client, files: dict[str, bytes], *, analyse: bool = True) -> dict:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("review-v2.zip", _archive(files), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    if analyse:
        assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
        assert run_analysis_jobs() == 1
    return repository


def _assert_forbidden_score_fields(value) -> None:
    forbidden = {
        "score",
        "scores",
        "overallScore",
        "categoryScore",
        "grade",
        "healthPercentage",
        "roadmap",
        "trend",
    }
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for nested in value.values():
            _assert_forbidden_score_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_forbidden_score_fields(nested)


def test_review_requires_authentication(client):
    response = client.get("/analysis/11111111-1111-1111-1111-111111111111/review")
    assert response.status_code == 401


def test_review_is_owner_scoped(auth_client, make_auth_headers):
    repository = _upload(auth_client, _FINDING_SOURCES)
    intruder = make_auth_headers("review-intruder@example.com")

    response = auth_client.get(
        f"/analysis/{repository['id']}/review",
        headers=intruder["headers"],
    )

    assert response.status_code == 404


def test_review_without_a_sealed_snapshot_returns_404(auth_client):
    repository = _upload(auth_client, _FINDING_SOURCES, analyse=False)

    response = auth_client.get(f"/analysis/{repository['id']}/review")

    assert response.status_code == 404


def test_review_contract_has_no_scores_and_is_deterministic(auth_client):
    repository = _upload(auth_client, _FINDING_SOURCES)

    first = auth_client.get(f"/analysis/{repository['id']}/review")
    second = auth_client.get(f"/analysis/{repository['id']}/review")

    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    body = first.json()
    _assert_forbidden_score_fields(body)
    assert body["schemaVersion"] == "engineering-review.v2"
    assert body["repositoryId"] == repository["id"]
    assert body["revisionValue"] == repository["revision"]["value"]
    assert body["snapshotSchemaVersion"] == "ri.v1"
    assert body["canonicalGraphHash"].startswith("sha256:")
    assert body["manifestDigest"].startswith("sha256:")
    assert body["provenance"]["source"] == "ri.v1"
    assert body["assessmentStatus"] == "partially_assessed"
    assert len({item["id"] for item in body["findings"]}) == len(body["findings"])


def test_every_public_finding_has_same_snapshot_evidence_that_opens(auth_client):
    repository = _upload(auth_client, _FINDING_SOURCES)
    review = auth_client.get(f"/analysis/{repository['id']}/review").json()

    assert review["findings"], "fixture must produce a supported resolver diagnostic"
    assert review["summary"]["unsupportedFindingCount"] == 0
    for finding in review["findings"]:
        assert finding["supportStatus"] == "supported"
        assert finding["snapshotId"] == review["snapshotId"]
        assert finding["evidence"]["snapshotId"] == review["snapshotId"]
        assert finding["factId"] == finding["evidence"]["factId"]
        assert finding["evidenceId"] == finding["evidence"]["evidenceId"]
        source = auth_client.get(
            f"/analysis/{repository['id']}/evidence",
            params={
                "snapshotId": finding["snapshotId"],
                "factId": finding["factId"],
                "path": finding["path"],
                "startLine": finding["startLine"],
                "endLine": finding["endLine"],
            },
        )
        assert source.status_code == 200, source.text
        assert source.json()["status"] == "ready"


def test_review_wrong_repository_evidence_fails_closed(auth_client):
    repository_a = _upload(auth_client, _FINDING_SOURCES)
    finding = auth_client.get(f"/analysis/{repository_a['id']}/review").json()["findings"][0]
    repository_b = _upload(auth_client, {"README.md": b"# other revision\n"})

    response = auth_client.get(
        f"/analysis/{repository_b['id']}/evidence",
        params={
            "snapshotId": finding["snapshotId"],
            "factId": finding["factId"],
            "path": finding["path"],
            "startLine": finding["startLine"],
            "endLine": finding["endLine"],
        },
    )

    assert response.status_code == 404


def test_review_category_matrix_and_honest_empty_finding_state(auth_client):
    repository = _upload(auth_client, _EMPTY_SOURCES)
    body = auth_client.get(f"/analysis/{repository['id']}/review").json()

    assert body["findings"] == []
    assert body["summary"]["evidenceBackedFindingCount"] == 0
    assert "0 evidence-backed findings" in body["summary"]["message"]
    categories = {item["id"]: item for item in body["categories"]}
    assert set(categories) == {
        "architecture_boundaries",
        "relationship_resolution",
        "source_extraction",
        "dependency_declarations",
        "security_vulnerability_scanning",
        "authentication_evidence",
        "repository_structure",
        "analysis_integrity",
    }
    assert categories["analysis_integrity"]["state"] == "assessed"
    assert categories["dependency_declarations"]["state"] == "insufficient_evidence"
    assert categories["security_vulnerability_scanning"]["state"] == "not_assessed"
    assert all("score" not in item["explanation"].lower() for item in categories.values())


def test_review_rejects_an_unsupported_snapshot_schema(auth_client):
    repository = _upload(auth_client, _EMPTY_SOURCES, analyse=False)

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        store = SnapshotStore(session)
        snapshot = store.begin(
            repository_id=record.id,
            revision=Revision(record.revision_kind, record.revision_value, record.revision_ref),
            schema_version="ri.v99",
            producer_version_set=["repository-inventory@1.1.0"],
        )
        store.add_node(
            snapshot,
            node_kind="repository",
            stable_key="repo:root",
            name="repository",
            language=None,
            evidence=[
                Evidence(
                    path="README.md",
                    start_line=1,
                    end_line=1,
                    logical_line_count=2,
                    extractor="repository-inventory",
                    extractor_version="1.1.0",
                )
            ],
        )
        store.seal(snapshot)

    response = auth_client.get(f"/analysis/{repository['id']}/review")
    assert response.status_code == 422
