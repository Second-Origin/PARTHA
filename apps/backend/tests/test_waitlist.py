from app.core.database import SessionLocal
from app.models.waitlist_entry import WaitlistEntry


def test_join_waitlist_records_a_new_signup(client):
    response = client.post("/waitlist", json={"email": "interested@example.com", "name": "Jane Doe"})

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}

    with SessionLocal() as db:
        entry = db.query(WaitlistEntry).filter_by(email="interested@example.com").one()
        assert entry.name == "Jane Doe"


def test_join_waitlist_does_not_require_a_name(client):
    response = client.post("/waitlist", json={"email": "no-name@example.com"})

    assert response.status_code == 201
    with SessionLocal() as db:
        entry = db.query(WaitlistEntry).filter_by(email="no-name@example.com").one()
        assert entry.name is None


def test_join_waitlist_normalizes_email_case_and_whitespace(client):
    client.post("/waitlist", json={"email": "  Mixed.Case@Example.com  "})

    with SessionLocal() as db:
        assert db.query(WaitlistEntry).filter_by(email="mixed.case@example.com").one() is not None


def test_join_waitlist_is_idempotent_for_a_repeat_signup(client):
    """A visitor resubmitting the form must never see an error (#334) --
    same 201/"ok" response, and no duplicate row."""
    first = client.post("/waitlist", json={"email": "repeat@example.com", "name": "First Name"})
    second = client.post("/waitlist", json={"email": "repeat@example.com", "name": "Different Name"})

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json() == {"status": "ok"}

    with SessionLocal() as db:
        entries = db.query(WaitlistEntry).filter_by(email="repeat@example.com").all()
        assert len(entries) == 1
        # First submission wins; a resubmission is a no-op, not an update.
        assert entries[0].name == "First Name"


def test_join_waitlist_rejects_an_invalid_email(client):
    response = client.post("/waitlist", json={"email": "not-an-email"})

    assert response.status_code == 422


def test_join_waitlist_requires_no_authentication(client):
    # No Authorization header attached -- unlike `auth_client`, `client` is
    # not pre-authenticated, which is exactly the point of this assertion.
    response = client.post("/waitlist", json={"email": "anonymous@example.com"})

    assert response.status_code == 201
