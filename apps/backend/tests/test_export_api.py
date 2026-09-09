import base64
import io
import json
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
                        "sample/src/main.tsx": "import React from 'react';\n",
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


def _export(auth_client, repository_id: str, target: str, fmt: str):
    return auth_client.post(
        "/export",
        json={"repositoryId": repository_id, "target": target, "format": fmt},
    )


def test_export_review_json_parses(auth_client):
    repository_id = _import_sample(auth_client)

    response = _export(auth_client, repository_id, "review", "json")

    assert response.status_code == 200
    body = response.json()
    assert body["encoding"] == "utf-8"
    assert body["mediaType"] == "application/json"
    assert body["filename"].endswith(".json")
    payload = json.loads(body["content"])
    assert payload["schemaVersion"] == "engineering-review.v2"
    assert "summary" in payload
    assert "overallScore" not in payload["summary"]
    assert "score" not in payload


def test_export_review_markdown_has_headings(auth_client):
    repository_id = _import_sample(auth_client)

    response = _export(auth_client, repository_id, "review", "markdown")

    assert response.status_code == 200
    body = response.json()
    assert body["mediaType"] == "text/markdown"
    assert body["filename"].endswith(".md")
    assert "# Engineering Review" in body["content"]
    assert "## Executive Summary" in body["content"]
    assert "## Category Assessment" in body["content"]
    assert "Overall Score" not in body["content"]


def test_export_review_html_is_valid_structure(auth_client):
    repository_id = _import_sample(auth_client)

    response = _export(auth_client, repository_id, "review", "html")

    assert response.status_code == 200
    body = response.json()
    assert body["mediaType"] == "text/html"
    content = body["content"]
    assert content.startswith("<!DOCTYPE html>")
    assert "<table>" in content
    assert "</html>" in content
    assert "Engineering Review" in content


def test_export_review_pdf_starts_with_pdf_header(auth_client):
    repository_id = _import_sample(auth_client)

    response = _export(auth_client, repository_id, "review", "pdf")

    assert response.status_code == 200
    body = response.json()
    assert body["encoding"] == "base64"
    assert body["mediaType"] == "application/pdf"
    assert body["filename"].endswith(".pdf")
    assert base64.b64decode(body["content"])[:5] == b"%PDF-"


def test_export_review_before_analysis_cannot_report_a_clean_result(auth_client):
    repository_id = _import_sample(auth_client, analyse=False)

    for fmt in ("json", "markdown"):
        response = _export(auth_client, repository_id, "review", fmt)
        error = assert_error_response(response, 404, "not_found")
        assert error.message == "No sealed Repository Intelligence snapshot is available for this repository."


def test_export_json_supported_for_every_target(auth_client):
    repository_id = _import_sample(auth_client)

    for target in ("documentation", "architecture", "dependencies"):
        response = _export(auth_client, repository_id, target, "json")
        assert response.status_code == 200, target
        body = response.json()
        assert body["encoding"] == "utf-8"
        json.loads(body["content"])  # must be valid JSON


def test_dependency_exports_report_assessments_as_not_computed(auth_client):
    repository_id = _import_sample(auth_client)

    json_response = _export(auth_client, repository_id, "dependencies", "json")
    markdown_response = _export(auth_client, repository_id, "dependencies", "markdown")

    assert json_response.status_code == 200
    payload = json.loads(json_response.json()["content"])
    assert payload["vulnerabilityAssessment"] == {"status": "not_computed"}
    assert payload["outdatedAssessment"] == {"status": "not_computed"}
    assert "vulnerabilities" not in payload
    assert "outdated" not in payload

    assert markdown_response.status_code == 200
    report = markdown_response.json()["content"]
    assert "| Vulnerability assessment | Not computed |" in report
    assert "| Outdated-version assessment | Not computed |" in report
    assert "outside the current analysis scope" in report


def test_export_non_review_targets_support_all_formats(auth_client):
    repository_id = _import_sample(auth_client)

    for target in ("documentation", "architecture", "dependencies"):
        markdown = _export(auth_client, repository_id, target, "markdown")
        assert markdown.status_code == 200, target
        assert markdown.json()["mediaType"] == "text/markdown"
        assert markdown.json()["content"].startswith("# "), target

        html = _export(auth_client, repository_id, target, "html")
        assert html.status_code == 200, target
        assert html.json()["mediaType"] == "text/html"
        assert html.json()["content"].startswith("<!DOCTYPE html>"), target
        assert "</html>" in html.json()["content"], target

        pdf = _export(auth_client, repository_id, target, "pdf")
        assert pdf.status_code == 200, target
        assert pdf.json()["encoding"] == "base64"
        assert pdf.json()["mediaType"] == "application/pdf"
        assert base64.b64decode(pdf.json()["content"])[:5] == b"%PDF-", target


def test_export_rejects_invalid_format(auth_client):
    repository_id = _import_sample(auth_client)

    response = _export(auth_client, repository_id, "review", "xml")

    error = assert_error_response(response, 422, "request_validation_error")
    assert error.details is not None
    assert "errors" in error.details


def test_export_missing_repository_returns_not_found(auth_client):
    response = _export(auth_client, "00000000-0000-0000-0000-000000000000", "review", "json")

    assert_error_response(response, 404, "not_found")
