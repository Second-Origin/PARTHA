"""Public Dependency Graph v2 contract and provenance tests (#158).

Mirrors the shape of tests/test_engineering_review_v2.py: Dependency Graph is
now a sealed-snapshot consumer with no legacy fallback, the same as
Architecture/Review/Insights.
"""

from __future__ import annotations

import io
import json
import zipfile

from tests.analysis_helpers import run_analysis_jobs


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload(auth_client, files: dict[str, bytes], *, analyse: bool = True) -> dict:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("dependency-v2.zip", _archive(files), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    if analyse:
        assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
        assert run_analysis_jobs() == 1
    return repository


_SOURCES_WITH_DEPENDENCIES = {
    "README.md": b"# dependency fixture\n",
    "apps/frontend/package.json": json.dumps(
        {"dependencies": {"react": "^18.3.0"}, "devDependencies": {"vitest": "^1.0.0"}}
    ).encode(),
}
_SOURCES_WITHOUT_DEPENDENCIES = {"README.md": b"# no manifests here\n"}


def test_dependencies_requires_authentication(client):
    response = client.get("/analysis/11111111-1111-1111-1111-111111111111/dependencies")
    assert response.status_code == 401


def test_dependencies_is_owner_scoped(auth_client, make_auth_headers):
    repository = _upload(auth_client, _SOURCES_WITH_DEPENDENCIES)
    intruder = make_auth_headers("dependencies-intruder@example.com")

    response = auth_client.get(f"/analysis/{repository['id']}/dependencies", headers=intruder["headers"])

    assert response.status_code == 404


def test_dependencies_without_a_sealed_snapshot_returns_404(auth_client):
    repository = _upload(auth_client, _SOURCES_WITH_DEPENDENCIES, analyse=False)

    response = auth_client.get(f"/analysis/{repository['id']}/dependencies")

    assert response.status_code == 404


def test_dependencies_contract_is_snapshot_bound_and_deterministic(auth_client):
    repository = _upload(auth_client, _SOURCES_WITH_DEPENDENCIES)

    first = auth_client.get(f"/analysis/{repository['id']}/dependencies")
    second = auth_client.get(f"/analysis/{repository['id']}/dependencies")

    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    body = first.json()
    assert body["schemaVersion"] == "dependency-graph.v2"
    assert body["repositoryId"] == repository["id"]
    assert body["revisionValue"] == repository["revision"]["value"]
    assert body["snapshotSchemaVersion"] == "ri.v1"
    assert body["canonicalGraphHash"].startswith("sha256:")
    assert body["manifestDigest"].startswith("sha256:")
    assert body["provenance"]["source"] == "ri.v1"
    assert body["provenance"]["snapshotId"] == body["snapshotId"]
    assert body["vulnerabilityAssessment"] == {"status": "not_computed"}
    assert body["outdatedAssessment"] == {"status": "not_computed"}


def test_dependencies_reports_real_nodes_edges_and_declarations(auth_client):
    repository = _upload(auth_client, _SOURCES_WITH_DEPENDENCIES)

    body = auth_client.get(f"/analysis/{repository['id']}/dependencies").json()

    nodes = {node["id"]: node for node in body["nodes"]}
    assert set(nodes) == {"dep:npm:react", "dep:npm:vitest"}
    react = nodes["dep:npm:react"]
    assert react["name"] == "react"
    assert react["version"] == "^18.3.0"
    assert react["type"] == "production"
    assert react["ecosystem"] == "npm"
    assert react["declarations"] == [
        {
            "name": "react",
            "manifestPath": "apps/frontend/package.json",
            "workspacePath": "apps/frontend",
            "startLine": 1,
            "endLine": 1,
            "extractor": "dependency-manifest",
            "extractorVersion": "1.2.0",
            "ecosystem": "npm",
            "version": "^18.3.0",
            "type": "production",
        }
    ]
    assert nodes["dep:npm:vitest"]["type"] == "development"

    assert body["totalDependencies"] == 2
    assert body["manifestCount"] == 1
    assert len(body["edges"]) == 2
    for edge in body["edges"]:
        assert edge["source"] == "repo:root"
        assert edge["target"] in nodes
        assert edge["type"] == "depends-on"


def test_dependencies_evidence_backed_edges_open_through_the_evidence_endpoint(auth_client):
    """A dependency declaration citation must resolve like any other evidence (#95/#154 pattern)."""

    repository = _upload(auth_client, _SOURCES_WITH_DEPENDENCIES)
    body = auth_client.get(f"/analysis/{repository['id']}/dependencies").json()
    declaration = next(node for node in body["nodes"] if node["id"] == "dep:npm:react")["declarations"][0]

    source = auth_client.get(
        f"/analysis/{repository['id']}/evidence",
        params={
            "snapshotId": body["snapshotId"],
            "factId": "dep:npm:react",
            "path": declaration["manifestPath"],
            "startLine": declaration["startLine"],
            "endLine": declaration["endLine"],
        },
    )
    assert source.status_code == 200, source.text
    assert source.json()["status"] == "ready"


def test_dependencies_a_genuine_zero_dependency_snapshot_is_a_200_not_a_404(auth_client):
    repository = _upload(auth_client, _SOURCES_WITHOUT_DEPENDENCIES)

    response = auth_client.get(f"/analysis/{repository['id']}/dependencies")

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"] == []
    assert body["edges"] == []
    assert body["totalDependencies"] == 0
    assert body["manifestCount"] == 0


def test_dependencies_diagnostics_pass_through_and_stay_distinguishable_from_zero_results(auth_client):
    repository = _upload(
        auth_client,
        {
            "README.md": b"# malformed fixture\n",
            "apps/broken/package.json": b"{",
        },
    )

    body = auth_client.get(f"/analysis/{repository['id']}/dependencies").json()

    assert body["nodes"] == []
    assert body["diagnostics"] == [
        {
            "code": "RI-SRC-MALFORMED",
            "category": "malformed source",
            "severity": "error",
            "message": "dependency manifest could not be parsed or has an unsupported structure",
            "path": "apps/broken/package.json",
            "producer": "dependency-manifest@1.2.0",
            "details": None,
        }
    ]
    assert body["manifestCount"] == 1


def test_dependencies_across_two_manifests_are_preserved_as_separate_declarations(auth_client):
    """Regression coverage that #158 actually depends on the #156 fix."""

    repository = _upload(
        auth_client,
        {
            "README.md": b"# monorepo fixture\n",
            "apps/backend/pyproject.toml": b'[project]\ndependencies = [\n  "requests==2.31.0",\n]\n',
            "services/worker/requirements.txt": b"requests>=2.32\n",
        },
    )

    body = auth_client.get(f"/analysis/{repository['id']}/dependencies").json()

    node = next(item for item in body["nodes"] if item["id"] == "dep:pypi:requests")
    assert node["version"] is None  # conflicting versions: never silently pick one
    assert node["type"] == "production"
    assert {declaration["version"] for declaration in node["declarations"]} == {"==2.31.0", ">=2.32"}
    assert {declaration["manifestPath"] for declaration in node["declarations"]} == {
        "apps/backend/pyproject.toml",
        "services/worker/requirements.txt",
    }
    assert body["manifestCount"] == 2
