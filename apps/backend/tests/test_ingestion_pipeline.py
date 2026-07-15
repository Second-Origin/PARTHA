import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from app.github.client import GitHubClient
from app.core.exceptions import TimeoutServiceError


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _tar_gz_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(path)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _upload(auth_client, filename: str, content: bytes):
    return auth_client.post(
        "/repositories/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_zip_upload_persists_repository_and_analysis_completes(auth_client):
    response = _upload(
        auth_client,
        "sample.zip",
        _zip_bytes(
            {
                "sample/package.json": '{"dependencies":{"react":"^18.0.0"}}',
                "sample/src/main.tsx": "import React from 'react';",
                "sample/README.md": "# Sample",
            }
        ),
    )

    assert response.status_code == 201
    repository = response.json()
    assert repository["name"] == "sample"
    assert repository["status"] == "analysing"
    assert repository["analysisStage"] == "building-file-tree"
    assert repository["analysisProgress"] == 70
    assert repository["meta"]["framework"] == "React"
    # Uploads have no git history, so a stable content hash stands in as the
    # commit-addressability identifier (T9 / F2).
    assert repository["commitSha"].startswith("sha256:")

    start_response = auth_client.post(f"/analysis/{repository['id']}/start")
    assert start_response.status_code == 200
    assert start_response.json() == {"repositoryId": repository["id"], "status": "completed"}

    status_response = auth_client.get(f"/analysis/{repository['id']}/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "completed"
    assert status["stage"] == "completed"
    assert status["progress"] == 100
    assert status["completedAt"] is not None

    list_response = auth_client.get("/repositories")
    assert list_response.status_code == 200
    repositories = list_response.json()["data"]
    assert repositories[0]["id"] == repository["id"]
    assert repositories[0]["status"] == "completed"


def test_dependency_endpoint_reports_uncomputed_assessments_without_clean_claims(auth_client):
    response = _upload(
        auth_client,
        "historical-dependency.zip",
        _zip_bytes(
            {
                "historical-dependency/package.json": '{"dependencies":{"lodash":"4.17.15"}}',
                "historical-dependency/src/main.js": "const lodash = require('lodash');",
            }
        ),
    )
    assert response.status_code == 201
    repository_id = response.json()["id"]
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200

    dependency_response = auth_client.get(f"/analysis/{repository_id}/dependencies")

    assert dependency_response.status_code == 200
    payload = dependency_response.json()
    assert payload["vulnerabilityAssessment"] == {"status": "not_computed"}
    assert payload["outdatedAssessment"] == {"status": "not_computed"}
    assert any(node["name"] == "lodash" and node["version"] == "4.17.15" for node in payload["nodes"])
    assert payload["edges"]

    serialized_keys = {
        key
        for value in _walk_json(payload)
        if isinstance(value, dict)
        for key in value
    }
    assert serialized_keys.isdisjoint(
        {
            "has_vulnerabilities",
            "hasVulnerabilities",
            "is_outdated",
            "isOutdated",
            "vulnerabilities",
            "outdated",
        }
    )


def test_empty_dependency_endpoint_still_reports_uncomputed_assessments(auth_client):
    response = _upload(
        auth_client,
        "empty-dependencies.zip",
        _zip_bytes({"empty-dependencies/package.json": "{}"}),
    )
    assert response.status_code == 201
    repository_id = response.json()["id"]
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200

    dependency_response = auth_client.get(f"/analysis/{repository_id}/dependencies")

    assert dependency_response.status_code == 200
    payload = dependency_response.json()
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["totalDependencies"] == 0
    assert payload["vulnerabilityAssessment"] == {"status": "not_computed"}
    assert payload["outdatedAssessment"] == {"status": "not_computed"}


def _walk_json(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def test_tar_gz_upload_is_supported(auth_client):
    response = _upload(
        auth_client,
        "python-service.tar.gz",
        _tar_gz_bytes(
            {
                "python-service/requirements.txt": "fastapi==0.115.0\n",
                "python-service/app/main.py": "from fastapi import FastAPI\n",
            }
        ),
    )

    assert response.status_code == 201
    repository = response.json()
    assert repository["name"] == "python-service"
    assert repository["status"] == "analysing"
    assert repository["meta"]["framework"] == "FastAPI"


def test_invalid_archive_returns_backend_validation_error(auth_client):
    response = _upload(auth_client, "broken.zip", b"not an archive")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Unsupported archive format. Upload a ZIP or TAR archive."


def test_empty_archive_is_rejected(auth_client):
    response = _upload(auth_client, "empty.zip", _zip_bytes({}))

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Repository archive does not contain any readable files."


def test_duplicate_upload_name_returns_conflict(auth_client):
    content = _zip_bytes({"repo/package.json": "{}"})

    first = _upload(auth_client, "repo.zip", content)
    second = _upload(auth_client, "repo.zip", content)

    assert first.status_code == 201
    assert second.status_code == 409
    body = second.json()
    assert body["code"] == "conflict_error"
    assert body["message"] == "Repository has already been imported."
    assert body["details"]["name"] == "repo"


def test_github_import_uses_backend_validation_and_duplicate_detection(auth_client, monkeypatch: pytest.MonkeyPatch):
    def fake_clone(_: GitHubClient, __: str, destination: Path, ___: str | None = None) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}', encoding="utf-8")
        (destination / "src").mkdir()
        (destination / "src" / "main.tsx").write_text("import React from 'react';", encoding="utf-8")

    monkeypatch.setattr(GitHubClient, "clone_public_repository", fake_clone)

    first = auth_client.post("/repositories/github", json={"url": "https://github.com/example/demo"})
    duplicate = auth_client.post("/repositories/github", json={"url": "https://github.com/example/demo"})
    malformed_branch = auth_client.post(
        "/repositories/github",
        json={"url": "https://github.com/example/other", "branch": "../main"},
    )

    assert first.status_code == 201
    assert first.json()["status"] == "analysing"
    assert duplicate.status_code == 409
    assert malformed_branch.status_code == 422
    assert malformed_branch.json()["message"] == "Branch name contains unsupported characters."


def test_github_clone_timeout_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import subprocess

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)

    from app.core.config import Settings

    auth_client = GitHubClient(Settings(clone_timeout_seconds=1))
    with pytest.raises(TimeoutServiceError):
        auth_client.clone_public_repository("https://github.com/example/demo", tmp_path / "demo")


def test_github_clone_over_size_limit_aborts_and_cleans_up(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import subprocess

    from app.core.config import Settings
    from app.core.exceptions import ValidationServiceError

    destination = tmp_path / "demo"

    def fake_run(*args, **kwargs):
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "big.bin").write_bytes(b"x" * 4096)
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    auth_client = GitHubClient(Settings(max_clone_size_bytes=1024))
    with pytest.raises(ValidationServiceError):
        auth_client.clone_public_repository("https://github.com/example/demo", destination)

    # Over-limit clone must be removed from disk.
    assert not destination.exists()
