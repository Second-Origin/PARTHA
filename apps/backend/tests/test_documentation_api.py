import io
import zipfile

from tests.analysis_helpers import run_analysis_jobs
from tests.api_assertions import assert_error_response


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _import_sample(auth_client, *, analyse: bool = True) -> str:
    response = auth_client.post(
        "/repositories/upload",
        files={
            "file": (
                "sample.zip",
                _zip_bytes(
                    {
                        "sample/package.json": '{"dependencies":{"react":"^18.0.0"}}',
                        "sample/src/main.tsx": (
                            "import React from 'react';\n"
                            "const router = createBrowserRouter([{ path: '/users', element: null }]);\n"
                        ),
                        "sample/README.md": "# Sample\n",
                    }
                ),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 201
    repository_id = response.json()["id"]
    if analyse:
        assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200
        assert run_analysis_jobs() == 1
    return repository_id


def _generate(auth_client, repository_id: str, fmt: str):
    return auth_client.post("/documentation/generate", json={"repositoryId": repository_id, "format": fmt})


def _upload_and_analyse(auth_client, files: dict[str, str]) -> str:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("architecture.zip", _zip_bytes(files), "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    repository_id = response.json()["id"]
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200
    assert run_analysis_jobs() == 1
    return repository_id


def _markdown_section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    start = markdown.index(marker)
    rest = markdown[start + len(marker) :]
    next_marker = rest.find("\n## ")
    return rest if next_marker == -1 else rest[:next_marker]


def test_documentation_markdown_has_structured_headings(auth_client):
    repository_id = _import_sample(auth_client)

    response = _generate(auth_client, repository_id, "markdown")

    assert response.status_code == 200
    content = response.json()["content"]
    assert "## Overview" in content
    assert "## Architecture" in content
    assert "## Folder Structure" in content
    assert "## API" in content
    assert "## Environment" in content
    assert "## Deployment" in content
    assert "## Contribution" in content
    assert "react: ^18.0.0 (package.json)" in content
    assert "Observed route: /users" in content
    body = response.json()
    assert body["source"] == "ri.v1"
    assert body["snapshotSchemaVersion"] == "ri.v1"
    assert body["snapshotId"]
    assert body["revisionKind"] == "upload"
    assert body["revisionValue"].startswith("sha256:")
    assert "Sealed ri.v1 snapshot" in content


def test_documentation_html_renders_real_elements(auth_client):
    repository_id = _import_sample(auth_client)

    response = _generate(auth_client, repository_id, "html")

    assert response.status_code == 200
    content = response.json()["content"]
    assert content.startswith("<!DOCTYPE html>")
    assert "<h2>Overview</h2>" in content
    assert "</html>" in content


def test_documentation_returns_the_standard_error_for_a_missing_repository(auth_client):
    response = _generate(auth_client, "00000000-0000-0000-0000-000000000000", "markdown")

    assert_error_response(response, 404, "not_found")


def test_documentation_returns_404_without_a_sealed_snapshot(auth_client):
    repository_id = _import_sample(auth_client, analyse=False)

    response = _generate(auth_client, repository_id, "markdown")

    error = assert_error_response(response, 404, "not_found")
    assert "sealed Repository Intelligence snapshot" in error.message


def test_documentation_architecture_groups_modules_into_layers_from_snapshot_facts(auth_client):
    repository_id = _upload_and_analyse(
        auth_client,
        {
            "src/controllers/user_controller.ts": (
                "import { getUser } from '../services/user_service';\nexport const handler = () => getUser();\n"
            ),
            "src/services/user_service.ts": "export function getUser() { return 1; }\n",
        },
    )

    response = _generate(auth_client, repository_id, "markdown")

    assert response.status_code == 200
    architecture = _markdown_section(response.json()["content"], "Architecture")
    assert "Presentation" in architecture
    assert "Business Logic" in architecture
    assert "Presentation → Business Logic: 1 observed relationship(s)" in architecture


def test_documentation_architecture_reports_shared_layer_for_unclassified_repository(auth_client):
    repository_id = _upload_and_analyse(
        auth_client,
        {
            "assets/logo.svg": "<svg></svg>\n",
            "data/sample.csv": "a,b\n1,2\n",
        },
    )

    response = _generate(auth_client, repository_id, "markdown")

    assert response.status_code == 200
    architecture = _markdown_section(response.json()["content"], "Architecture")
    assert "Shared" in architecture
    assert "No cross-layer relationships observed in the supported snapshot facts." in architecture


def test_documentation_deployment_section_matches_real_deployment_yaml_only(auth_client):
    repository_id = _upload_and_analyse(
        auth_client,
        {
            "docker-compose.yml": "services:\n  api:\n    image: sample\n",
            ".github/workflows/ci.yml": "name: CI\non: push\n",
            "Dockerfile": "FROM python:3.12\n",
            "config/app.yaml": "debug: true\n",
        },
    )

    response = _generate(auth_client, repository_id, "markdown")

    assert response.status_code == 200
    deployment = _markdown_section(response.json()["content"], "Deployment")
    assert "docker-compose.yml" in deployment
    assert ".github/workflows/ci.yml" in deployment
    assert "Dockerfile" in deployment
    assert "config/app.yaml" not in deployment


def test_documentation_api_section_excludes_test_fixture_routes(auth_client):
    """Reproduces the 2026-08-20 audit finding that generated API
    documentation listed benchmark test-fixture routes (e.g. /config,
    /test) undistinguished from real API routes (#337)."""

    repository_id = _upload_and_analyse(
        auth_client,
        {
            "src/routes.py": (
                "from fastapi import FastAPI\n\n"
                "app = FastAPI()\n\n\n"
                '@app.get("/users")\n'
                "def list_users():\n"
                "    return []\n"
            ),
            "tests/fixtures/routes.py": (
                "from fastapi import FastAPI\n\n"
                "app = FastAPI()\n\n\n"
                '@app.get("/config")\n'
                "def config():\n"
                "    return {}\n\n\n"
                '@app.get("/test")\n'
                "def test_route():\n"
                "    return {}\n"
            ),
        },
    )

    response = auth_client.post(
        "/documentation/generate",
        json={"repositoryId": repository_id, "format": "markdown", "sections": ["api"]},
    )

    assert response.status_code == 200, response.text
    api_section = _markdown_section(response.json()["content"], "API")
    assert "/users" in api_section
    assert "src/routes.py" in api_section
    assert "/config" not in api_section
    assert "/test" not in api_section
    assert "tests/fixtures/routes.py" not in api_section


def test_documentation_is_owner_scoped(auth_client, make_auth_headers):
    repository_id = _import_sample(auth_client)
    other = make_auth_headers("other-docs@example.com")

    response = auth_client.post(
        "/documentation/generate",
        headers=other["headers"],
        json={"repositoryId": repository_id, "format": "markdown"},
    )

    assert_error_response(response, 404, "not_found")
