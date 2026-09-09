"""HTTP-level coverage for `GET /repositories/{id}/lineage` (#299, RFC-0002; #400).

Lineage allocation itself (sequence numbers, canonical-key grouping, the
duplicate-commit and concurrency cases) is already covered by
test_repository_lineage_service.py and test_repository_lineage_concurrency.py.
This file is scoped to the read surface: what the endpoint returns for a
standalone import, for each member of a real multi-import lineage, and that
it stays owner-scoped like every other repository route.
"""

import uuid
from pathlib import Path

import pytest

from app.github.client import GitHubClient


def _fake_clone(_: GitHubClient, __: str, destination: Path, ___: str | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "README.md").write_text("# demo\n", encoding="utf-8")


def _mock_github(monkeypatch: pytest.MonkeyPatch, commits: list[str], ref: str = "refs/heads/main") -> None:
    commit_iter = iter(commits)
    monkeypatch.setattr(GitHubClient, "clone_public_repository", _fake_clone)
    monkeypatch.setattr(GitHubClient, "read_head_commit", lambda *_: next(commit_iter))
    monkeypatch.setattr(GitHubClient, "read_head_ref", lambda *_: ref)


def _seed_upload(owner_id: str, name: str = "standalone-repo") -> str:
    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        repository_id = str(uuid.uuid4())
        db.add(
            RepositoryRecord(
                id=repository_id,
                owner_id=owner_id,
                name=name,
                source="upload",
                local_path=f"/tmp/{repository_id}",
                status="completed",
            )
        )
        db.commit()
        return repository_id
    finally:
        db.close()


def test_standalone_upload_has_no_lineage_and_lists_only_itself(auth_client):
    repository_id = _seed_upload(auth_client.default_user["id"])

    response = auth_client.get(f"/repositories/{repository_id}/lineage")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["isLineaged"] is False
    assert body["lineageId"] is None
    assert body["canonicalSourceKey"] is None
    assert body["canonicalBranch"] is None
    assert [entry["repositoryId"] for entry in body["entries"]] == [repository_id]
    assert body["entries"][0]["isCurrent"] is True
    assert body["entries"][0]["sequence"] is None


def test_lineaged_repository_lists_every_member_most_recent_first(auth_client, monkeypatch: pytest.MonkeyPatch):
    _mock_github(monkeypatch, ["a" * 40, "b" * 40, "c" * 40])

    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    second = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    third = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert first.status_code == second.status_code == third.status_code == 201

    response = auth_client.get(f"/repositories/{third.json()['id']}/lineage")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["isLineaged"] is True
    assert body["canonicalSourceKey"] == "github.com/acme/widgets"
    assert body["canonicalBranch"] == "refs/heads/main"

    entries = body["entries"]
    assert [entry["repositoryId"] for entry in entries] == [
        third.json()["id"],
        second.json()["id"],
        first.json()["id"],
    ]
    assert [entry["sequence"] for entry in entries] == [3, 2, 1]
    assert [entry["isCurrent"] for entry in entries] == [True, False, False]
    assert entries[0]["revision"]["value"] == "c" * 40
    assert entries[2]["revision"]["value"] == "a" * 40


def test_lineaged_repository_read_from_an_older_member_flips_which_entry_is_current(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    _mock_github(monkeypatch, ["a" * 40, "b" * 40])

    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    second = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert first.status_code == second.status_code == 201

    response = auth_client.get(f"/repositories/{first.json()['id']}/lineage")

    assert response.status_code == 200, response.text
    body = response.json()
    entries = {entry["repositoryId"]: entry for entry in body["entries"]}
    assert len(entries) == 2
    assert entries[first.json()["id"]]["isCurrent"] is True
    assert entries[second.json()["id"]]["isCurrent"] is False


def test_lineage_endpoint_returns_404_for_another_owners_repository(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")
    repository_id = _seed_upload(alice["user"]["id"])

    denied = client.get(f"/repositories/{repository_id}/lineage", headers=bob["headers"])
    assert denied.status_code == 404

    allowed = client.get(f"/repositories/{repository_id}/lineage", headers=alice["headers"])
    assert allowed.status_code == 200


def test_lineage_endpoint_returns_404_for_a_nonexistent_repository(auth_client):
    response = auth_client.get(f"/repositories/{uuid.uuid4()}/lineage")
    assert response.status_code == 404
