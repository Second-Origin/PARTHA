"""Service-level coverage for #299 (RFC-0002): live import/delete lineage
allocation, ownership, and the cyclic FK's real enforcement.

HTTP-level tests exercise the actual `/repositories/github` and
`/repositories/upload` routes with a faked git clone (same idiom as
test_ingestion_pipeline.py), so lineage assignment is proven end to end, not
just at the repository-layer unit. Repository-layer tests exercise
`RepositoryRepository.add_with_lineage`/`delete_with_lineage_update`
directly for cases an HTTP request can't force (a same-lineage race, a
deliberately-forced FK violation).
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.database import SessionLocal
from app.github.client import GitHubClient
from app.models.repository import RepositoryRecord
from app.models.repository_lineage import RepositoryLineage
from app.repositories.repository_repository import RepositoryRepository
from tests.api_assertions import assert_error_response


def _fake_clone(_: GitHubClient, __: str, destination: Path, ___: str | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "README.md").write_text("# demo\n", encoding="utf-8")


def _mock_github(monkeypatch: pytest.MonkeyPatch, commits: list[str], ref: str = "refs/heads/main") -> None:
    commit_iter = iter(commits)
    monkeypatch.setattr(GitHubClient, "clone_public_repository", _fake_clone)
    monkeypatch.setattr(GitHubClient, "read_head_commit", lambda *_: next(commit_iter))
    monkeypatch.setattr(GitHubClient, "read_head_ref", lambda *_: ref)


def _lineage_of(response_json: dict) -> tuple[str | None, int | None]:
    with SessionLocal() as db:
        record = db.get(RepositoryRecord, response_json["id"])
        assert record is not None
        return record.lineage_id, record.sequence


# --------------------------------------------------------------------------
# Live import: lineage assignment
# --------------------------------------------------------------------------


def test_first_github_import_creates_a_lineage_with_sequence_one(auth_client, monkeypatch: pytest.MonkeyPatch):
    _mock_github(monkeypatch, ["a" * 40])

    response = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})

    assert response.status_code == 201, response.text
    lineage_id, sequence = _lineage_of(response.json())
    assert lineage_id is not None
    assert sequence == 1
    with SessionLocal() as db:
        lineage = db.get(RepositoryLineage, lineage_id)
        assert lineage is not None
        assert lineage.canonical_source_key == "github.com/acme/widgets"
        assert lineage.canonical_branch == "refs/heads/main"
        assert lineage.display_name == "widgets"
        assert lineage.latest_repository_id == response.json()["id"]
        assert lineage.next_sequence == 2


def test_second_commit_on_same_source_and_ref_reuses_the_lineage_and_increments(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    _mock_github(monkeypatch, ["a" * 40, "b" * 40])

    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    second = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})

    assert first.status_code == 201 and second.status_code == 201
    first_lineage, first_sequence = _lineage_of(first.json())
    second_lineage, second_sequence = _lineage_of(second.json())
    assert first_lineage == second_lineage
    assert (first_sequence, second_sequence) == (1, 2)
    with SessionLocal() as db:
        lineage = db.get(RepositoryLineage, first_lineage)
        assert lineage.latest_repository_id == second.json()["id"]
        assert lineage.next_sequence == 3


def test_owner_repo_case_variants_of_the_same_url_match_the_same_lineage(auth_client, monkeypatch: pytest.MonkeyPatch):
    """Live validation allows mixed-case owner/repo (only the host must be
    exact-case), so two spellings of the same repository must still land in
    the same lineage once case-folded (#299 §8.1)."""
    _mock_github(monkeypatch, ["a" * 40, "b" * 40])

    first = auth_client.post("/repositories/github", json={"url": "https://github.com/Acme/Widgets"})
    second = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})

    assert first.status_code == 201 and second.status_code == 201
    first_lineage, _ = _lineage_of(first.json())
    second_lineage, second_sequence = _lineage_of(second.json())
    assert first_lineage == second_lineage
    assert second_sequence == 2


def test_different_ref_gets_a_different_lineage(auth_client, monkeypatch: pytest.MonkeyPatch):
    _mock_github(monkeypatch, ["a" * 40], ref="refs/heads/main")
    main_response = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    _mock_github(monkeypatch, ["b" * 40], ref="refs/heads/dev")
    dev_response = auth_client.post(
        "/repositories/github", json={"url": "https://github.com/acme/widgets", "branch": "dev"}
    )

    assert main_response.status_code == 201 and dev_response.status_code == 201
    main_lineage, _ = _lineage_of(main_response.json())
    dev_lineage, dev_sequence = _lineage_of(dev_response.json())
    assert main_lineage != dev_lineage
    assert dev_sequence == 1


def test_different_repository_gets_a_different_lineage(auth_client, monkeypatch: pytest.MonkeyPatch):
    _mock_github(monkeypatch, ["a" * 40, "b" * 40])

    widgets = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    gadgets = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/gadgets"})

    assert widgets.status_code == 201 and gadgets.status_code == 201
    widgets_lineage, _ = _lineage_of(widgets.json())
    gadgets_lineage, gadgets_sequence = _lineage_of(gadgets.json())
    assert widgets_lineage != gadgets_lineage
    assert gadgets_sequence == 1


def test_different_owner_gets_a_different_lineage_even_for_the_same_source_and_ref(
    auth_client, make_auth_headers, monkeypatch: pytest.MonkeyPatch
):
    _mock_github(monkeypatch, ["a" * 40])
    primary = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert primary.status_code == 201

    other = make_auth_headers("other-owner@example.com")
    _mock_github(monkeypatch, ["a" * 40])
    other_response = auth_client.post(
        "/repositories/github", json={"url": "https://github.com/acme/widgets"}, headers=other["headers"]
    )

    assert other_response.status_code == 201
    primary_lineage, _ = _lineage_of(primary.json())
    other_lineage, other_sequence = _lineage_of(other_response.json())
    assert primary_lineage != other_lineage
    assert other_sequence == 1
    with SessionLocal() as db:
        assert db.get(RepositoryLineage, other_lineage).owner_id == other["user"]["id"]


def test_same_commit_is_allowed_in_two_different_branch_lineages(auth_client, monkeypatch: pytest.MonkeyPatch):
    shared_commit = "c" * 40
    _mock_github(monkeypatch, [shared_commit], ref="refs/heads/main")
    main_response = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    _mock_github(monkeypatch, [shared_commit], ref="refs/heads/release")
    release_response = auth_client.post(
        "/repositories/github", json={"url": "https://github.com/acme/widgets", "branch": "release"}
    )

    assert main_response.status_code == 201
    assert release_response.status_code == 201
    assert main_response.json()["revision"]["value"] == shared_commit
    assert release_response.json()["revision"]["value"] == shared_commit
    main_lineage, _ = _lineage_of(main_response.json())
    release_lineage, _ = _lineage_of(release_response.json())
    assert main_lineage != release_lineage


def test_the_same_commit_twice_in_one_lineage_is_still_rejected_as_a_duplicate(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    """The pre-existing 409 behaviour must survive #299's rewrite of the
    persistence path -- this is the authoritative, transactional duplicate
    check now, not the old owner+source_url pre-clone check."""
    _mock_github(monkeypatch, ["a" * 40, "a" * 40])

    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    duplicate = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})

    assert first.status_code == 201
    error = assert_error_response(duplicate, 409, "conflict_error")
    assert error.details == {"repositoryId": first.json()["id"], "name": first.json()["name"]}

    with SessionLocal() as db:
        lineage_id, _ = _lineage_of(first.json())
        lineage = db.get(RepositoryLineage, lineage_id)
        # The rejected duplicate must not have burned a sequence number.
        assert lineage.next_sequence == 2


def test_upload_never_creates_or_touches_a_lineage(auth_client):
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("demo.zip", _minimal_zip(), "application/octet-stream")},
    )

    assert response.status_code == 201, response.text
    lineage_id, sequence = _lineage_of(response.json())
    assert (lineage_id, sequence) == (None, None)


def _minimal_zip() -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.md", "# demo\n")
    return buffer.getvalue()


def test_a_failed_lineage_duplicate_insert_cleans_up_the_staged_repository_directory(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    """#299 §5.3 extends the existing pre-clone cleanup across the
    transactional insert phase: a rejected duplicate must not leave an
    orphaned directory under storage."""
    _mock_github(monkeypatch, ["a" * 40, "a" * 40])

    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert first.status_code == 201

    from app.core.config import get_settings
    from app.storage.local import LocalStorage

    storage = LocalStorage(get_settings())
    before = set(storage.repositories_root.iterdir()) if storage.repositories_root.exists() else set()

    duplicate = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert duplicate.status_code == 409

    after = set(storage.repositories_root.iterdir()) if storage.repositories_root.exists() else set()
    assert after == before, "the duplicate's staged directory must be removed, not left behind"


# --------------------------------------------------------------------------
# Deletion: latest-pointer rollback
# --------------------------------------------------------------------------


def test_deleting_a_non_latest_member_leaves_the_latest_pointer_unchanged(auth_client, monkeypatch: pytest.MonkeyPatch):
    _mock_github(monkeypatch, ["a" * 40, "b" * 40, "c" * 40])
    auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    second = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    third = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    lineage_id, _ = _lineage_of(third.json())

    delete_response = auth_client.delete(f"/repositories/{second.json()['id']}")
    assert delete_response.status_code == 204

    with SessionLocal() as db:
        lineage = db.get(RepositoryLineage, lineage_id)
        assert lineage.latest_repository_id == third.json()["id"]
        assert lineage.next_sequence == 4  # counter never decreases


def test_deleting_the_latest_member_rolls_back_to_the_next_highest_surviving_sequence(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    _mock_github(monkeypatch, ["a" * 40, "b" * 40, "c" * 40])
    first = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    second = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    third = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    lineage_id, _ = _lineage_of(first.json())

    delete_response = auth_client.delete(f"/repositories/{third.json()['id']}")
    assert delete_response.status_code == 204

    with SessionLocal() as db:
        lineage = db.get(RepositoryLineage, lineage_id)
        assert lineage.latest_repository_id == second.json()["id"]
        assert lineage.next_sequence == 4


def test_deleting_the_last_member_keeps_an_empty_lineage_and_never_reuses_its_sequence(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    _mock_github(monkeypatch, ["a" * 40])
    only = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    lineage_id, _ = _lineage_of(only.json())

    delete_response = auth_client.delete(f"/repositories/{only.json()['id']}")
    assert delete_response.status_code == 204

    with SessionLocal() as db:
        lineage = db.get(RepositoryLineage, lineage_id)
        assert lineage is not None, "an empty lineage is kept, not garbage collected"
        assert lineage.latest_repository_id is None
        assert lineage.next_sequence == 2

    _mock_github(monkeypatch, ["b" * 40])
    reimport = auth_client.post("/repositories/github", json={"url": "https://github.com/acme/widgets"})
    assert reimport.status_code == 201
    reimport_lineage, reimport_sequence = _lineage_of(reimport.json())
    assert reimport_lineage == lineage_id
    assert reimport_sequence == 2  # sequence 1 is never reused


# --------------------------------------------------------------------------
# Cross-owner isolation
# --------------------------------------------------------------------------


def test_cross_owner_lineage_lookup_never_matches_another_owners_row(auth_client, make_auth_headers):
    """A pre-existing lineage owned by another user, with the exact same
    canonical key a fresh import will compute, must never be reused --
    proven through the real allocation path (`add_with_lineage`), not by
    asserting a private lookup helper's return value in isolation."""
    other = make_auth_headers("owner-b@example.com")
    with SessionLocal() as db:
        other_lineage = RepositoryLineage(
            id=str(uuid.uuid4()),
            owner_id=other["user"]["id"],
            canonical_source_key="github.com/shared/repo",
            canonical_branch="refs/heads/main",
            display_name="repo",
            latest_repository_id=None,
            next_sequence=1,
            created_at=datetime.now(UTC),
        )
        db.add(other_lineage)
        db.commit()
        other_lineage_id = other_lineage.id

    with SessionLocal() as db:
        repository_repo = RepositoryRepository(db)
        record = RepositoryRecord(
            id=str(uuid.uuid4()),
            owner_id=auth_client.default_user["id"],  # type: ignore[attr-defined]
            name="repo",
            source="github",
            source_url="https://github.com/shared/repo",
            branch="main",
            revision_kind="git",
            revision_value="e" * 40,
            revision_ref="refs/heads/main",
            local_path="/tmp/x",
            status="analysing",
        )
        persisted = repository_repo.add_with_lineage(
            record,
            owner_id=auth_client.default_user["id"],  # type: ignore[attr-defined]
            canonical_source_key="github.com/shared/repo",
            canonical_branch="refs/heads/main",
            display_name="repo",
        )
        assert persisted.lineage_id != other_lineage_id
        assert persisted.sequence == 1


def test_cross_owner_lineage_attachment_is_rejected_by_the_database_even_if_forced(auth_client, make_auth_headers):
    """The composite deferred FK enforces ownership even if application code
    is wrong (#299 §9) -- proven here by deliberately bypassing the service
    layer and trying to attach a repository to another owner's lineage
    directly."""
    other = make_auth_headers("owner-c@example.com")
    with SessionLocal() as db:
        lineage = RepositoryLineage(
            id=str(uuid.uuid4()),
            owner_id=other["user"]["id"],
            canonical_source_key="github.com/other/repo2",
            canonical_branch="refs/heads/main",
            display_name="repo2",
            latest_repository_id=None,
            next_sequence=1,
            created_at=datetime.now(UTC),
        )
        db.add(lineage)
        db.commit()
        lineage_id = lineage.id

    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with SessionLocal() as db:
        # Force enforcement on this exact connection rather than relying on
        # app.core.database's process-wide connect-event listener having
        # already fired (it normally has, by this point in a real app or a
        # full test run, but that's an accident of import order/platform,
        # not something this specific assertion should depend on -- must be
        # the very first statement on the connection, before SQLite's
        # autobegin opens a transaction, since the pragma is a no-op once
        # one is open).
        db.execute(text("PRAGMA foreign_keys=ON"))
        record = RepositoryRecord(
            id=str(uuid.uuid4()),
            owner_id=auth_client.default_user["id"],  # type: ignore[attr-defined]
            name="cross-owner-attempt",
            source="github",
            source_url="https://github.com/other/repo2",
            branch="main",
            revision_kind="git",
            revision_value="d" * 40,
            revision_ref="refs/heads/main",
            local_path="/tmp/x",
            status="analysing",
            lineage_id=lineage_id,
            sequence=1,
        )
        db.add(record)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
