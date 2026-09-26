"""The repository's own metadata agrees with the Architecture summary (#475).

Upload-time detection reads only the repository root, so a monorepo was
recorded as framework "Unknown" with no entry point while the Architecture
view, reading the sealed snapshot, named both.
"""

from __future__ import annotations

import io
import json
import zipfile

from tests.analysis_helpers import run_analysis_jobs

_MONOREPO = {
    "README.md": b"# monorepo\n",
    "frontend/package.json": json.dumps({"name": "web", "dependencies": {"react": "19.0.0"}}).encode(),
    "frontend/src/main.tsx": b"export const boot = () => 1;\n",
    "backend/requirements.txt": b"fastapi==0.115.0\n",
    "backend/app/__init__.py": b"",
    "backend/app/main.py": b"from fastapi import FastAPI\n\napp = FastAPI()\n",
}


def _analyse(auth_client, files: dict[str, bytes]) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    response = auth_client.post("/repositories/upload", files={"file": ("m.zip", buffer.getvalue(), "application/zip")})
    assert response.status_code == 201, response.text
    repository_id = response.json()["id"]
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200
    assert run_analysis_jobs() == 1
    return repository_id


def test_repository_meta_matches_the_architecture_summary_for_a_monorepo(auth_client):
    repository_id = _analyse(auth_client, _MONOREPO)

    meta = auth_client.get(f"/repositories/{repository_id}").json()["meta"]
    summary = auth_client.get(f"/analysis/{repository_id}/architecture").json()["summary"]

    assert summary["framework"] == "FastAPI, React"
    assert meta["framework"] == summary["framework"]
    assert meta["language"] == summary["language"]
    assert summary["entryPoint"] is not None
    assert meta["entryPoint"] == summary["entryPoint"]


def test_a_value_the_snapshot_cannot_supply_keeps_the_upload_time_one(auth_client):
    repository_id = _analyse(auth_client, {"README.md": b"# docs only\n", "notes.txt": b"hello\n"})

    meta = auth_client.get(f"/repositories/{repository_id}").json()["meta"]

    assert meta["framework"] == "Unknown"
    assert meta["entryPoint"] is None
