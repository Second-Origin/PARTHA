"""The flagship prototype journey, end to end (#154).

Register -> import -> identify the revision -> run durable analysis -> explore
the architecture -> ask the authentication question -> receive an
evidence-backed answer -> open its source -> verify the revision manifest ->
prove a second owner is locked out.

Each surface has its own focused tests elsewhere. This one exists because the
prototype's claim is that these steps connect: a citation shown at the end must
belong to the snapshot sealed in the middle, for the revision identified at the
start. Testing the steps in isolation cannot catch that seam breaking.
"""

from __future__ import annotations

import io
import zipfile

from tests.analysis_helpers import run_analysis_jobs

# A genuinely connected guard chain: a route depends on a guard, which reaches a
# service, which reaches a model. Plus an unguarded /health route that must
# never be claimed as authentication-relevant.
_SOURCES = {
    "README.md": b"# journey fixture\n",
    "requirements.txt": b"fastapi==0.115.0\n",
    "src/dependencies.py": (
        b"from src.services import UserService\n\n\n"
        b"def get_current_user(token: str) -> dict:\n"
        b"    return UserService(token)\n"
    ),
    "src/services.py": (
        b"from src.models import UserModel\n\n\ndef UserService(token: str) -> dict:\n    return UserModel(token)\n"
    ),
    "src/models.py": b"def UserModel(token: str) -> dict:\n    return {'token': token}\n",
    "src/routes.py": (
        b"from fastapi import Depends, FastAPI\n"
        b"from src.dependencies import get_current_user\n\n"
        b"app = FastAPI()\n\n\n"
        b'@app.get("/me")\n'
        b"def me(user=Depends(get_current_user)) -> dict:\n"
        b"    return user\n\n\n"
        b'@app.get("/health")\n'
        b"def health() -> dict:\n"
        b"    return {'status': 'ok'}\n"
    ),
}


def _archive() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in _SOURCES.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_evidence_backed_prototype_journey(auth_client, make_auth_headers):
    # 1. Anonymous access is refused before anything else happens.
    assert auth_client.get("/repositories", headers={"Authorization": ""}).status_code == 401

    # 2. Import a repository.
    upload = auth_client.post(
        "/repositories/upload",
        files={"file": ("journey.zip", _archive(), "application/zip")},
    )
    assert upload.status_code == 201, upload.text
    repository = upload.json()
    repository_id = repository["id"]

    # 3. The exact revision is identified at import time, before any analysis.
    revision = repository["revision"]
    assert revision["kind"] == "upload"
    assert revision["value"].startswith("sha256:")

    # 4. Analysis is durable: submitting enqueues, draining the worker completes.
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200
    assert run_analysis_jobs() == 1
    status = auth_client.get(f"/analysis/{repository_id}/status").json()
    assert status["status"] == "completed"

    # 5. The architecture comes from a sealed snapshot, not the working tree.
    architecture = auth_client.get(f"/analysis/{repository_id}/architecture").json()
    snapshot_id = architecture["relationshipSnapshotId"]
    assert snapshot_id
    assert architecture["nodes"]

    # 6. The authentication question returns an evidence-backed answer.
    explanation = auth_client.get(f"/analysis/{repository_id}/architecture/authentication").json()
    assert explanation["status"] == "ready"
    assert explanation["snapshotId"] == snapshot_id
    claims = explanation["claims"]
    assert claims

    # The unguarded route must not be claimed as authentication-relevant.
    assert not any(claim["name"] == "/health" for claim in claims)

    # 7. Every citation belongs to the snapshot the manifest will name.
    citations = [item for claim in claims for item in claim["evidence"]]
    assert citations
    assert all(item["snapshotId"] == snapshot_id for item in citations)

    # 8. A citation opens real source, verified against the sealed content.
    cited = citations[0]
    source = auth_client.get(
        f"/analysis/{repository_id}/evidence",
        params={
            "snapshotId": cited["snapshotId"],
            "factId": cited["factId"],
            "path": cited["path"],
            "startLine": cited["startLine"],
            "endLine": cited["endLine"],
        },
    ).json()
    assert source["status"] == "ready"
    assert source["content"]
    assert source["revisionValue"] == revision["value"]

    # 9. A fabricated fact id against a real snapshot must not resolve. This is
    # the "a real citation on an unsupported claim is still invalid" rule.
    forged = auth_client.get(
        f"/analysis/{repository_id}/evidence",
        params={
            "snapshotId": snapshot_id,
            "factId": "fabricated::fact",
            "path": cited["path"],
            "startLine": cited["startLine"],
            "endLine": cited["endLine"],
        },
    ).json()
    assert forged["status"] == "unavailable"
    assert forged["content"] is None

    # 10. The revision manifest names that same snapshot and verifies.
    manifest_response = auth_client.get(f"/analysis/{repository_id}/revision-manifest").json()
    manifest = manifest_response["manifest"]
    assert manifest["snapshotId"] == snapshot_id
    assert manifest["revisionValue"] == revision["value"]
    assert manifest_response["verificationState"] == "verified"

    verified = auth_client.post(
        f"/analysis/{repository_id}/revision-manifest/verify",
        json={"manifest": manifest, "manifestDigest": manifest_response["manifestDigest"]},
    ).json()
    assert verified["verificationState"] == "verified"

    # 11. Dependency Graph is snapshot-bound too (#158): it shares the exact
    # same snapshot identity proven above, not a separate legacy inventory.
    dependencies = auth_client.get(f"/analysis/{repository_id}/dependencies").json()
    assert dependencies["schemaVersion"] == "dependency-graph.v2"
    assert dependencies["snapshotId"] == snapshot_id
    assert dependencies["provenance"]["source"] == "ri.v1"
    fastapi = next(node for node in dependencies["nodes"] if node["id"] == "dep:pypi:fastapi")
    assert fastapi["declarations"][0]["manifestPath"] == "requirements.txt"

    # 12. A second owner reaches none of it, and sees an empty list.
    intruder = make_auth_headers("journey-intruder@example.com")
    for path in (
        f"/repositories/{repository_id}",
        f"/analysis/{repository_id}/architecture",
        f"/analysis/{repository_id}/architecture/authentication",
        f"/analysis/{repository_id}/revision-manifest",
    ):
        assert auth_client.get(path, headers=intruder["headers"]).status_code == 404

    listed = auth_client.get("/repositories", headers=intruder["headers"]).json()
    assert listed["data"] == []


def test_journey_answer_is_not_simulated_without_a_provider(auth_client):
    """The AI path must fail closed rather than invent an answer."""

    upload = auth_client.post(
        "/repositories/upload",
        files={"file": ("journey.zip", _archive(), "application/zip")},
    )
    repository_id = upload.json()["id"]
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200
    assert run_analysis_jobs() == 1

    response = auth_client.post(
        "/ai/query",
        json={"repositoryId": repository_id, "query": "How does authentication work?"},
    )

    assert response.status_code == 422
    assert "not configured" in response.text.lower()


def test_journey_reports_honest_state_before_a_snapshot_exists(auth_client):
    """A repository with no sealed snapshot must not look analysed."""

    upload = auth_client.post(
        "/repositories/upload",
        files={"file": ("journey.zip", _archive(), "application/zip")},
    )
    repository_id = upload.json()["id"]
    # Enqueue but do not drain the worker: no snapshot is sealed.
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200

    # Architecture 404s rather than falling back to a graph built from unsealed
    # repository metadata (#217) -- the same honest contract as the manifest below.
    assert auth_client.get(f"/analysis/{repository_id}/architecture").status_code == 404

    explanation = auth_client.get(f"/analysis/{repository_id}/architecture/authentication").json()
    assert explanation["status"] == "missing_snapshot"
    assert explanation["claims"] == []

    # The manifest must refuse to name a revision it cannot evidence.
    assert auth_client.get(f"/analysis/{repository_id}/revision-manifest").status_code == 404
