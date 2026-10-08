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


def test_stale_compatibility_metadata_cannot_override_sealed_stack(auth_client):
    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord

    repository_id = _analyse(auth_client, _MONOREPO)
    with SessionLocal() as db:
        record = db.get(RepositoryRecord, repository_id)
        record.repo_metadata = {
            **record.repo_metadata,
            "framework": "Unknown",
            "language": "Unknown",
            "entryPoint": None,
        }
        db.commit()
    meta = auth_client.get(f"/repositories/{repository_id}").json()["meta"]
    summary = auth_client.get(f"/analysis/{repository_id}/architecture").json()["summary"]
    assert meta["framework"] == summary["framework"] == "FastAPI, React"
    assert meta["language"] == summary["language"]
    assert meta["entryPoint"] == summary["entryPoint"]
    with SessionLocal() as db:
        # Read projection does not mutate compatibility metadata or sealed rows.
        assert db.get(RepositoryRecord, repository_id).repo_metadata["framework"] == "Unknown"


def test_unknown_snapshot_stack_does_not_keep_upload_guess(auth_client):
    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord

    repository_id = _analyse(auth_client, {"README.md": b"# docs only\n"})
    with SessionLocal() as db:
        record = db.get(RepositoryRecord, repository_id)
        record.repo_metadata = {**record.repo_metadata, "framework": "React", "entryPoint": "old.ts"}
        db.commit()
    meta = auth_client.get(f"/repositories/{repository_id}").json()["meta"]
    assert meta["framework"] == "Unknown"
    assert meta["entryPoint"] is None


def test_post_seal_stale_lease_recovery_keeps_overview_consistent(auth_client):
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models.analysis_job import AnalysisJob
    from app.models.repository import RepositoryRecord
    from app.workers.analysis_worker import AnalysisWorker

    repository_id = _analyse(auth_client, _MONOREPO)
    with SessionLocal() as db:
        job = db.scalars(select(AnalysisJob).where(AnalysisJob.repository_id == repository_id)).one()
        job.status = "running"
        job.stage = "sealing"
        job.worker_id = "lost-worker"
        job.lease_expires_at = datetime.now(UTC) - timedelta(minutes=10)
        record = db.get(RepositoryRecord, repository_id)
        record.status = "analysing"
        record.repo_metadata = {**record.repo_metadata, "framework": "Unknown"}
        db.commit()
    assert AnalysisWorker(SessionLocal, worker_id="recovery-worker", lease_seconds=60).sweep_stale() == 1
    overview = auth_client.get(f"/repositories/{repository_id}").json()
    summary = auth_client.get(f"/analysis/{repository_id}/architecture").json()["summary"]
    assert overview["status"] == "completed"
    assert overview["meta"]["framework"] == summary["framework"] == "FastAPI, React"
