import io
import zipfile


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _import_sample(client) -> str:
    response = client.post(
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


def _generate(client, repository_id: str, fmt: str):
    return client.post("/documentation/generate", json={"repositoryId": repository_id, "format": fmt})


def test_documentation_markdown_has_structured_headings(client):
    repository_id = _import_sample(client)

    response = _generate(client, repository_id, "markdown")

    assert response.status_code == 200
    content = response.json()["content"]
    assert "## Overview" in content
    assert "## Architecture" in content


def test_documentation_html_renders_real_elements(client):
    repository_id = _import_sample(client)

    response = _generate(client, repository_id, "html")

    assert response.status_code == 200
    content = response.json()["content"]
    assert content.startswith("<!DOCTYPE html>")
    assert "<h2>Overview</h2>" in content
    assert "</html>" in content
