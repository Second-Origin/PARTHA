import base64
import io
import json
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


def _export(client, repository_id: str, target: str, fmt: str):
    return client.post(
        "/export",
        json={"repositoryId": repository_id, "target": target, "format": fmt},
    )


def test_export_review_json_parses(client):
    repository_id = _import_sample(client)

    response = _export(client, repository_id, "review", "json")

    assert response.status_code == 200
    body = response.json()
    assert body["encoding"] == "utf-8"
    assert body["mediaType"] == "application/json"
    assert body["filename"].endswith(".json")
    payload = json.loads(body["content"])
    assert "summary" in payload
    assert isinstance(payload["summary"]["overallScore"], int)


def test_export_review_markdown_has_headings(client):
    repository_id = _import_sample(client)

    response = _export(client, repository_id, "review", "markdown")

    assert response.status_code == 200
    body = response.json()
    assert body["mediaType"] == "text/markdown"
    assert body["filename"].endswith(".md")
    assert "# Engineering Review" in body["content"]
    assert "## Executive Summary" in body["content"]
    assert "| Overall Score |" in body["content"]


def test_export_review_html_is_valid_structure(client):
    repository_id = _import_sample(client)

    response = _export(client, repository_id, "review", "html")

    assert response.status_code == 200
    body = response.json()
    assert body["mediaType"] == "text/html"
    content = body["content"]
    assert content.startswith("<!DOCTYPE html>")
    assert "<table>" in content
    assert "</html>" in content
    assert "Engineering Review" in content


def test_export_review_pdf_starts_with_pdf_header(client):
    repository_id = _import_sample(client)

    response = _export(client, repository_id, "review", "pdf")

    assert response.status_code == 200
    body = response.json()
    assert body["encoding"] == "base64"
    assert body["mediaType"] == "application/pdf"
    assert body["filename"].endswith(".pdf")
    assert base64.b64decode(body["content"])[:5] == b"%PDF-"


def test_export_json_supported_for_every_target(client):
    repository_id = _import_sample(client)

    for target in ("documentation", "architecture", "dependencies"):
        response = _export(client, repository_id, target, "json")
        assert response.status_code == 200, target
        body = response.json()
        assert body["encoding"] == "utf-8"
        json.loads(body["content"])  # must be valid JSON


def test_export_pdf_not_available_for_non_review_target(client):
    repository_id = _import_sample(client)

    response = _export(client, repository_id, "dependencies", "pdf")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_export_rejects_invalid_format(client):
    repository_id = _import_sample(client)

    response = _export(client, repository_id, "review", "xml")

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_error"


def test_export_missing_repository_returns_not_found(client):
    response = _export(client, "00000000-0000-0000-0000-000000000000", "review", "json")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
