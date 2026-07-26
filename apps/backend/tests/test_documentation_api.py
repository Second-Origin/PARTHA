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


def test_documentation_is_owner_scoped(auth_client, make_auth_headers):
    repository_id = _import_sample(auth_client)
    other = make_auth_headers("other-docs@example.com")

    response = auth_client.post(
        "/documentation/generate",
        headers=other["headers"],
        json={"repositoryId": repository_id, "format": "markdown"},
    )

    assert_error_response(response, 404, "not_found")
