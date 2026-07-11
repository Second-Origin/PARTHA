import uuid

from sqlalchemy import select

ALICE = "alice@example.com"
BOB = "bob@example.com"


def _seed_repository(owner_email: str, name: str = "sample-repo") -> str:
    """Insert a repository owned by ``owner_email`` directly, bypassing the
    import pipeline, and return its id. The current-user seam resolves the same
    user by email, so requests carrying that X-Dev-User header own this row."""
    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord
    from app.models.user import User

    db = SessionLocal()
    try:
        owner = db.scalars(select(User).where(User.email == owner_email)).first()
        if owner is None:
            owner = User(id=str(uuid.uuid4()), email=owner_email)
            db.add(owner)
            db.commit()
            db.refresh(owner)
        repository_id = str(uuid.uuid4())
        db.add(
            RepositoryRecord(
                id=repository_id,
                owner_id=owner.id,
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


def test_get_returns_404_for_another_users_repository(client):
    repository_id = _seed_repository(ALICE)

    denied = client.get(f"/repositories/{repository_id}", headers={"X-Dev-User": BOB})
    assert denied.status_code == 404

    allowed = client.get(f"/repositories/{repository_id}", headers={"X-Dev-User": ALICE})
    assert allowed.status_code == 200
    assert allowed.json()["id"] == repository_id


def test_list_only_returns_the_current_users_repositories(client):
    _seed_repository(ALICE)

    alice_view = client.get("/repositories", headers={"X-Dev-User": ALICE})
    assert alice_view.status_code == 200
    assert alice_view.json()["total"] == 1

    bob_view = client.get("/repositories", headers={"X-Dev-User": BOB})
    assert bob_view.status_code == 200
    assert bob_view.json() == {"data": [], "total": 0}


def test_delete_returns_404_for_another_users_repository(client):
    repository_id = _seed_repository(ALICE)

    denied = client.delete(f"/repositories/{repository_id}", headers={"X-Dev-User": BOB})
    assert denied.status_code == 404

    # The repository still exists for its owner: the denial did not delete it.
    still_there = client.get(f"/repositories/{repository_id}", headers={"X-Dev-User": ALICE})
    assert still_there.status_code == 200


def test_default_seed_user_does_not_see_dev_users_repositories(client):
    _seed_repository(ALICE)

    # No X-Dev-User header -> the seed user, which owns none of Alice's data.
    seed_view = client.get("/repositories")
    assert seed_view.status_code == 200
    assert seed_view.json() == {"data": [], "total": 0}
