"""HTTP-level coverage for `POST /repositories/{id}/reanalyse` (#448).

Lineage allocation is already covered by test_repository_lineage_service.py
and test_repository_lineage_concurrency.py; this file is scoped to the new
affordance: what happens when the branch has moved, when it has not, when the
repository has no upstream at all, and that it stays owner-scoped.

The point of the feature is that "nothing has changed" is a state rather than
the `409 Repository has already been imported` a manual re-import used to
return, so the unmoved case asserts a 200 as deliberately as the moved one.
"""

import uuid
from pathlib import Path

import pytest

from app.github.client import GitHubClient


def _fake_clone(_: GitHubClient, __: str, destination: Path, ___: str | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "README.md").write_text("# demo\n", encoding="utf-8")


def _mock_github(
    monkeypatch: pytest.MonkeyPatch,
    commits: list[str],
    *,
    remote_head: str,
    ref: str = "refs/heads/main",
) -> None:
    """Clone the same tree every time, but hand out the given commit identities.

    `commits` is consumed one per import; `remote_head` is what `ls-remote`
    reports, which is the value re-analysis compares against.
    """

    commit_iter = iter(commits)
    monkeypatch.setattr(GitHubClient, "clone_public_repository", _fake_clone)
    monkeypatch.setattr(GitHubClient, "read_head_commit", lambda *_: next(commit_iter))
    monkeypatch.setattr(GitHubClient, "read_head_ref", lambda *_: ref)
    monkeypatch.setattr(GitHubClient, "read_remote_head_commit", lambda *_, **__: remote_head)


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


def test_an_unmoved_branch_reports_the_current_revision_rather_than_a_conflict(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    _mock_github(monkeypatch, ["a" * 40], remote_head="a" * 40)
    imported = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert imported.status_code == 201

    response = auth_client.post(f"/repositories/{imported.json()['id']}/reanalyse")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "already-current"
    assert body["remoteHead"] == "a" * 40
    assert body["previousRepositoryId"] is None
    # The repository returned is the one already sealed, so a caller can render
    # "you are current at <this revision>" without a second request.
    assert body["repository"]["id"] == imported.json()["id"]
    assert body["repository"]["revision"]["value"] == "a" * 40

    # Nothing was imported: the lineage still holds exactly one revision.
    lineage = auth_client.get(f"/repositories/{imported.json()['id']}/lineage").json()
    assert [entry["sequence"] for entry in lineage["entries"]] == [1]


def test_a_moved_branch_seals_a_new_revision_in_the_same_lineage(auth_client, monkeypatch: pytest.MonkeyPatch):
    _mock_github(monkeypatch, ["a" * 40, "b" * 40], remote_head="b" * 40)
    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert first.status_code == 201

    response = auth_client.post(f"/repositories/{first.json()['id']}/reanalyse")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "revision-imported"
    assert body["remoteHead"] == "b" * 40
    assert body["previousRepositoryId"] == first.json()["id"]
    assert body["repository"]["id"] != first.json()["id"]
    assert body["repository"]["revision"]["value"] == "b" * 40

    # Same lineage, new sequence, latest pointer advanced -- the history the
    # two-revision work (#219) needs, produced without retyping a URL.
    lineage = auth_client.get(f"/repositories/{body['repository']['id']}/lineage").json()
    assert lineage["isLineaged"] is True
    assert [entry["sequence"] for entry in lineage["entries"]] == [2, 1]
    assert [entry["repositoryId"] for entry in lineage["entries"]] == [
        body["repository"]["id"],
        first.json()["id"],
    ]


def test_reanalysing_an_older_member_still_compares_against_the_lineage_head(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    """Opening revision 1 of a two-revision lineage and asking to re-analyse
    must not report the branch as moved and import a third copy of something
    already sealed: the comparison is against the lineage's head, not against
    whichever revision the reader happens to be looking at."""

    _mock_github(monkeypatch, ["a" * 40, "b" * 40], remote_head="b" * 40)
    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    second = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert first.status_code == second.status_code == 201

    response = auth_client.post(f"/repositories/{first.json()['id']}/reanalyse")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "already-current"
    assert body["repository"]["id"] == second.json()["id"]

    lineage = auth_client.get(f"/repositories/{second.json()['id']}/lineage").json()
    assert [entry["sequence"] for entry in lineage["entries"]] == [2, 1]


def test_an_upload_has_no_upstream_and_says_so(auth_client):
    repository_id = _seed_upload(auth_client.default_user["id"])

    response = auth_client.post(f"/repositories/{repository_id}/reanalyse")

    assert response.status_code == 409, response.text
    # A refusal a reader can act on: it names why, not just that.
    body = response.json()
    assert body["code"] == "conflict_error"
    assert "upload" in body["message"].lower()
    assert body["details"]["source"] == "upload"


def test_reanalyse_returns_404_for_another_owners_repository(
    client, make_auth_headers, monkeypatch: pytest.MonkeyPatch
):
    _mock_github(monkeypatch, ["a" * 40], remote_head="a" * 40)
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")
    imported = client.post(
        "/repositories/github",
        json={"url": "https://github.com/acme/widgets"},
        headers=alice["headers"],
    )
    assert imported.status_code == 201
    repository_id = imported.json()["id"]

    # 404 rather than 403: a cross-owner request never learns the id exists.
    denied = client.post(f"/repositories/{repository_id}/reanalyse", headers=bob["headers"])
    assert denied.status_code == 404

    allowed = client.post(f"/repositories/{repository_id}/reanalyse", headers=alice["headers"])
    assert allowed.status_code == 200


def test_reanalyse_returns_404_for_a_nonexistent_repository(auth_client):
    response = auth_client.post(f"/repositories/{uuid.uuid4()}/reanalyse")
    assert response.status_code == 404


def test_an_unreadable_branch_head_is_reported_rather_than_guessed(auth_client, monkeypatch: pytest.MonkeyPatch):
    """A remote that answers with nothing this client understands must not be
    silently treated as "unchanged" -- that would report a repository as
    current on the strength of a failed lookup."""

    _mock_github(monkeypatch, ["a" * 40], remote_head="a" * 40)
    imported = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert imported.status_code == 201
    monkeypatch.setattr(GitHubClient, "read_remote_head_commit", lambda *_, **__: None)

    response = auth_client.post(f"/repositories/{imported.json()['id']}/reanalyse")

    assert response.status_code == 502, response.text
