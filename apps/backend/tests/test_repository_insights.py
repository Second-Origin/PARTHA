"""Authentic repository-insights.v1 endpoint tests (#154)."""

from __future__ import annotations

import io
import zipfile

from app.models.repository import RepositoryRecord

from tests.analysis_helpers import run_analysis_jobs

_SOURCES = {
    "README.md": b"# insights fixture\n",
    "package.json": b'{"dependencies":{"react":"18.3.0"}}\n',
    "src/index.ts": (
        b"import { helper } from './helper';\n"
        b"import { absent } from './absent';\n"
        b"export const value = helper() + absent();\n"
    ),
    "src/helper.ts": b"export function helper() { return 1; }\n",
}


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload(auth_client, files: dict[str, bytes] = _SOURCES, *, analyse: bool = True) -> dict:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("insights.zip", _archive(files), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    if analyse:
        assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
        assert run_analysis_jobs() == 1
    return repository


def test_insights_requires_authentication(client):
    response = client.get("/analysis/11111111-1111-1111-1111-111111111111/insights")
    assert response.status_code == 401


def test_insights_is_owner_scoped(auth_client, make_auth_headers):
    repository = _upload(auth_client)
    intruder = make_auth_headers("insights-intruder@example.com")

    response = auth_client.get(
        f"/analysis/{repository['id']}/insights",
        headers=intruder["headers"],
    )

    assert response.status_code == 404


def test_insights_without_a_sealed_snapshot_returns_404(auth_client):
    repository = _upload(auth_client, analyse=False)
    assert auth_client.get(f"/analysis/{repository['id']}/insights").status_code == 404


def test_insights_identity_definitions_ratios_and_order_are_deterministic(auth_client):
    repository = _upload(auth_client)

    first = auth_client.get(f"/analysis/{repository['id']}/insights")
    second = auth_client.get(f"/analysis/{repository['id']}/insights")

    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    body = first.json()
    assert body["schemaVersion"] == "repository-insights.v1"
    assert body["repositoryId"] == repository["id"]
    assert body["revisionValue"] == repository["revision"]["value"]
    assert body["snapshotSchemaVersion"] == "ri.v1"
    assert body["provenance"]["source"] == "ri.v1"
    assert body["canonicalGraphHash"].startswith("sha256:")
    assert body["manifestDigest"].startswith("sha256:")
    assert body["changeOverTime"] == {
        "assessmentState": "not_assessed",
        "message": "Change-over-time insights are not available yet.",
    }
    ids = [metric["id"] for metric in body["metrics"]]
    assert len(ids) == len(set(ids))
    assert all(metric["definition"] for metric in body["metrics"])
    assert all(metric["snapshotId"] == body["snapshotId"] for metric in body["metrics"])
    coverage = next(metric for metric in body["metrics"] if metric["id"] == "extraction.coverage")
    assert coverage["numerator"] is not None
    assert coverage["denominator"] is not None
    assert coverage["denominator"] > 0
    assert coverage["value"] == coverage["numerator"] / coverage["denominator"]


def test_seeded_insights_totals_are_exact_and_not_scores(auth_client):
    repository = _upload(auth_client)
    body = auth_client.get(f"/analysis/{repository['id']}/insights").json()
    metrics = {metric["id"]: metric for metric in body["metrics"]}

    # These totals are fixed by the four-file fixture and the TypeScript plus
    # manifest extractors; drift requires an intentional contract update.
    assert metrics["nodes.files.total"]["value"] == 4
    assert metrics["nodes.dependencies.total"]["value"] == 1
    assert metrics["diagnostics.relationships.unresolved"]["value"] >= 1
    assert metrics["evidence.records.total"]["value"] > 0
    assert metrics["assessment.vulnerability-scanning"]["value"] is None
    assert metrics["assessment.vulnerability-scanning"]["assessmentState"] == "not_assessed"
    prohibited = {
        "health",
        "quality",
        "maintainability",
        "productivity",
        "velocity",
        "security rating",
        "technical debt",
        "predicted effort",
        "top risk",
    }
    labels = " ".join(metric["label"].lower() for metric in body["metrics"])
    assert all(term not in labels for term in prohibited)


def test_insights_never_falls_back_to_mutable_legacy_metadata(auth_client):
    repository = _upload(auth_client)
    endpoint = f"/analysis/{repository['id']}/insights"
    before = auth_client.get(endpoint).json()

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        metadata = dict(record.repo_metadata or {})
        metadata["intelligence"] = {
            "files": [{"path": "fabricated.py"}],
            "healthScore": 100,
            "diagnostics": [{"code": "FABRICATED"}],
        }
        record.repo_metadata = metadata
        session.commit()

    assert auth_client.get(endpoint).json() == before
