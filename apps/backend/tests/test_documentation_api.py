import io
import zipfile

from tests.api_assertions import assert_error_response


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _import_sample(auth_client) -> str:
    response = auth_client.post(
        "/repositories/upload",
        files={
            "file": (
                "sample.zip",
                _zip_bytes(
                    {
                        "sample/package.json": '{"dependencies":{"react":"^18.0.0"}}',
                        "sample/src/main.tsx": "import React from 'react';\n",
                        "sample/README.md": "# Sample\n",
                    }
                ),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _generate(auth_client, repository_id: str, fmt: str):
    return auth_client.post("/documentation/generate", json={"repositoryId": repository_id, "format": fmt})


def test_documentation_markdown_has_structured_headings(auth_client):
    repository_id = _import_sample(auth_client)

    response = _generate(auth_client, repository_id, "markdown")

    assert response.status_code == 200
    content = response.json()["content"]
    assert "## Overview" in content
    assert "## Architecture" in content


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
