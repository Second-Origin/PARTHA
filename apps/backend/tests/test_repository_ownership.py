"""Owner-scoping of the repository routes, proven with real access tokens.

The pre-auth ``X-Dev-User`` fallback was removed in E1.3 (#63); ownership is now
established solely by the authenticated user behind the Bearer token. A repo is
seeded directly (bypassing the import pipeline) and attributed to a registered
user's id, so requests carrying that user's token own it.
"""

import uuid

from sqlalchemy import select

from tests.conftest import register_user


def _seed_repository(owner_id: str, name: str = "sample-repo") -> str:
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


def test_get_returns_404_for_another_users_repository(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")
    repository_id = _seed_repository(alice["user"]["id"])

    denied = client.get(f"/repositories/{repository_id}", headers=bob["headers"])
    assert denied.status_code == 404

    allowed = client.get(f"/repositories/{repository_id}", headers=alice["headers"])
    assert allowed.status_code == 200
    assert allowed.json()["id"] == repository_id


def test_list_only_returns_the_current_users_repositories(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")
    _seed_repository(alice["user"]["id"])

    alice_view = client.get("/repositories", headers=alice["headers"])
    assert alice_view.status_code == 200
    assert alice_view.json()["total"] == 1

    bob_view = client.get("/repositories", headers=bob["headers"])
    assert bob_view.status_code == 200
    assert bob_view.json() == {"data": [], "total": 0}


def test_delete_returns_404_for_another_users_repository(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")
    repository_id = _seed_repository(alice["user"]["id"])

    denied = client.delete(f"/repositories/{repository_id}", headers=bob["headers"])
    assert denied.status_code == 404

    # The repository still exists for its owner: the denial did not delete it.
    still_there = client.get(f"/repositories/{repository_id}", headers=alice["headers"])
    assert still_there.status_code == 200

    # And it was never removed from the database by the cross-user delete.
    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        assert db.scalars(select(RepositoryRecord).where(RepositoryRecord.id == repository_id)).first() is not None
    finally:
        db.close()


def test_unauthenticated_repository_access_is_rejected(client):
    # With the pre-auth fallback removed, no token means 401 — not an empty
    # list attributed to a seed user.
    assert client.get("/repositories").status_code == 401
    assert client.get(f"/repositories/{uuid.uuid4()}").status_code == 401


def test_registered_user_starts_with_no_repositories(client):
    auth = register_user(client, "fresh@example.com")
    view = client.get("/repositories", headers=auth["headers"])
    assert view.status_code == 200
    assert view.json() == {"data": [], "total": 0}
