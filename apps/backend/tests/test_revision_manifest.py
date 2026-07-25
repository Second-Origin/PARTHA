"""Revision manifest verification contract (#113).

The manifest is the product's answer to "which exact revision produced this,
and can I check that later". These tests hold it to that claim: the digest must
be reproducible for a sealed snapshot, tampering must be detected, another
owner must not be able to read it, and the citations a user follows must belong
to the revision the manifest names.
"""

from __future__ import annotations

import io
import zipfile

from app.analysis.manifest import build_manifest, manifest_digest
from app.models.repository import RepositoryRecord

from tests.analysis_helpers import run_analysis_jobs

_SOURCES = {
    "README.md": b"# manifest fixture\n",
    "package.json": b'{\n  "dependencies": {\n    "react": "18.3.0"\n  }\n}\n',
    "src/alpha/index.ts": (
        b"import { beta } from '../beta';\nexport const alpha = beta();\n"
    ),
    "src/beta/index.ts": b"export function beta() { return 1; }\n",
}


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _analysed_repository(auth_client) -> dict:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("manifest.zip", _archive(_SOURCES), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
    assert run_analysis_jobs() == 1
    return repository


def test_manifest_exposes_the_sealed_revision_identity(auth_client):
    repository = _analysed_repository(auth_client)

    response = auth_client.get(f"/analysis/{repository['id']}/revision-manifest")
    assert response.status_code == 200, response.text
    body = response.json()
    manifest = body["manifest"]

    assert manifest["schemaVersion"] == "revision-manifest.v1"
    assert manifest["repositoryId"] == repository["id"]
    assert manifest["snapshotSchemaVersion"] == "ri.v1"
    assert manifest["revisionKind"] == "upload"
    assert manifest["revisionValue"].startswith("sha256:")
    assert manifest["snapshotId"]
    assert manifest["canonicalGraphHash"]
    assert manifest["createdAt"]
    assert manifest["sealedAt"]

    # Extractors are named and versioned individually, not as opaque strings.
    assert manifest["extractors"]
    for extractor in manifest["extractors"]:
        assert extractor["name"]
        assert extractor["version"]

    assert body["manifestDigest"].startswith("sha256:")
    assert body["verificationState"] == "verified"
    assert body["verificationMethod"] == "sha256-canonical-json"


def test_manifest_never_claims_to_be_digitally_signed(auth_client):
    """A canonical hash is not a signature; the copy must not imply otherwise."""

    repository = _analysed_repository(auth_client)
    body = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()

    note = body["verificationNote"].lower()
    assert "not a digital signature" in note
    assert "signed" not in body["verificationMethod"].lower()


def test_same_sealed_snapshot_produces_the_same_manifest_digest(auth_client):
    """The digest is a pure function of sealed facts, stable across reads."""

    repository = _analysed_repository(auth_client)

    first = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()
    second = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()

    assert first["manifestDigest"] == second["manifestDigest"]
    assert first["manifest"] == second["manifest"]

    # Recomputing from the stored snapshot independently reproduces the digest,
    # so the value is not just cached alongside the response.
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        from app.intelligence.query_service import SnapshotQueryService

        snapshot = SnapshotQueryService(session, record.owner_id).latest_snapshot_for_owner(record.id)
        assert snapshot is not None
        assert manifest_digest(build_manifest(snapshot)) == first["manifestDigest"]


def test_verification_accepts_an_unaltered_manifest(auth_client):
    repository = _analysed_repository(auth_client)
    exported = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()

    response = auth_client.post(
        f"/analysis/{repository['id']}/revision-manifest/verify",
        json={"manifest": exported["manifest"], "manifestDigest": exported["manifestDigest"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verificationState"] == "verified"
    assert body["matchesStoredSnapshot"] is True
    assert body["mismatchedFields"] == []


def test_altered_manifest_content_fails_verification(auth_client):
    """Editing a field while keeping the original digest must be detected."""

    repository = _analysed_repository(auth_client)
    exported = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()

    tampered = dict(exported["manifest"])
    tampered["revisionValue"] = "sha256:" + "f" * 64

    response = auth_client.post(
        f"/analysis/{repository['id']}/revision-manifest/verify",
        json={"manifest": tampered, "manifestDigest": exported["manifestDigest"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verificationState"] == "mismatch"
    assert body["matchesStoredSnapshot"] is False


def test_manifest_rehashed_after_tampering_still_fails_against_stored_facts(auth_client):
    """A self-consistent forgery is still caught by comparing to the snapshot.

    Recomputing the digest over altered content defeats the digest check alone,
    so verification also compares the submitted body to the stored snapshot.
    """

    repository = _analysed_repository(auth_client)
    exported = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()

    from app.schemas.manifest import RevisionManifest

    tampered = dict(exported["manifest"])
    tampered["canonicalGraphHash"] = "sha256:" + "a" * 64
    forged_digest = manifest_digest(RevisionManifest.model_validate(tampered))

    response = auth_client.post(
        f"/analysis/{repository['id']}/revision-manifest/verify",
        json={"manifest": tampered, "manifestDigest": forged_digest},
    )

    body = response.json()
    assert body["verificationState"] == "mismatch"
    assert body["matchesStoredSnapshot"] is False
    assert "canonicalGraphHash" in body["mismatchedFields"]


def test_another_owner_cannot_retrieve_or_verify_the_manifest(auth_client, make_auth_headers):
    repository = _analysed_repository(auth_client)
    exported = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()

    intruder = make_auth_headers("intruder@example.com")

    read = auth_client.get(
        f"/analysis/{repository['id']}/revision-manifest",
        headers=intruder["headers"],
    )
    assert read.status_code == 404

    verify = auth_client.post(
        f"/analysis/{repository['id']}/revision-manifest/verify",
        headers=intruder["headers"],
        json={"manifest": exported["manifest"], "manifestDigest": exported["manifestDigest"]},
    )
    assert verify.status_code == 404


def test_manifest_requires_authentication(client):
    unauthenticated = client.get(
        "/analysis/11111111-1111-1111-1111-111111111111/revision-manifest"
    )
    assert unauthenticated.status_code == 401


def test_citations_reference_the_revision_the_manifest_names(auth_client):
    """The evidence a user opens must belong to the manifest's snapshot.

    This is the link that makes the manifest meaningful: if an explanation's
    citations pointed at a different snapshot, the revision identity would
    describe something other than the answer on screen.
    """

    repository = _analysed_repository(auth_client)
    manifest = auth_client.get(f"/analysis/{repository['id']}/revision-manifest").json()["manifest"]

    architecture = auth_client.get(f"/analysis/{repository['id']}/architecture").json()
    assert architecture["relationshipSnapshotId"] == manifest["snapshotId"]

    cited = [
        evidence
        for edge in architecture["edges"]
        for evidence in edge.get("evidence", [])
    ]
    assert cited, "expected at least one evidence-backed architecture edge"

    for evidence in cited:
        assert evidence["snapshotId"] == manifest["snapshotId"]

    # And the source behind a citation resolves against that same snapshot.
    sample = cited[0]
    source = auth_client.get(
        f"/analysis/{repository['id']}/evidence",
        params={
            "snapshotId": sample["snapshotId"],
            "factId": sample["factId"],
            "path": sample["path"],
            "startLine": sample["startLine"],
            "endLine": sample["endLine"],
        },
    )
    assert source.status_code == 200, source.text
    resolved = source.json()
    assert resolved["snapshotId"] == manifest["snapshotId"]
    assert resolved["revisionValue"] == manifest["revisionValue"]
