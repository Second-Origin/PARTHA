"""Coverage for verified account deletion (#290).

These tests exercise the real ``DELETE /auth/me`` endpoint end to end
(reauth, cascade, storage cleanup, cross-owner isolation) plus one
service-level test for the seed-user guard, which has no reachable HTTP path
since the seed user can never hold an access token.
"""

from pathlib import Path

from tests.conftest import DEFAULT_TEST_PASSWORD, register_user


def _delete(client, headers, password=DEFAULT_TEST_PASSWORD, confirm_email="alice@example.com"):
    return client.request(
        "DELETE",
        "/auth/me",
        headers=headers,
        json={"password": password, "confirmEmail": confirm_email},
    )


# --- reauthentication and confirmation -----------------------------------------


def test_delete_account_rejects_wrong_password(client):
    auth = register_user(client, "alice@example.com")

    response = _delete(client, auth["headers"], password="wrong-password-entirely")

    assert response.status_code == 401
    # The account must still exist and be usable.
    assert client.get("/auth/me", headers=auth["headers"]).status_code == 200


def test_delete_account_rejects_confirmation_email_mismatch(client):
    auth = register_user(client, "alice@example.com")

    response = _delete(client, auth["headers"], confirm_email="not-alice@example.com")

    assert response.status_code == 422
    assert client.get("/auth/me", headers=auth["headers"]).status_code == 200


def test_delete_account_confirmation_email_is_case_and_whitespace_insensitive(client):
    auth = register_user(client, "alice@example.com")

    response = _delete(client, auth["headers"], confirm_email="  Alice@Example.com  ")

    assert response.status_code == 204


# --- success path ---------------------------------------------------------------


def test_delete_account_succeeds_and_clears_the_refresh_cookie(client):
    auth = register_user(client, "alice@example.com")

    response = _delete(client, auth["headers"])

    assert response.status_code == 204
    set_cookie = response.headers.get("set-cookie", "")
    assert "partha_refresh=" in set_cookie
    # Deletion (expiry in the past / empty value) rather than a fresh session.
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


def test_deleted_account_can_no_longer_authenticate(client):
    auth = register_user(client, "alice@example.com")
    assert _delete(client, auth["headers"]).status_code == 204

    # The now-stale access token is rejected...
    assert client.get("/auth/me", headers=auth["headers"]).status_code == 401
    # ...and the account cannot log back in with its old credentials.
    login = client.post("/auth/login", json={"email": "alice@example.com", "password": DEFAULT_TEST_PASSWORD})
    assert login.status_code == 401


def test_repeated_deletion_request_is_a_safe_terminal_401(client):
    auth = register_user(client, "alice@example.com")
    assert _delete(client, auth["headers"]).status_code == 204

    # A second attempt with the same (now invalid) token must not 500 or
    # somehow re-run deletion; it fails the same way any stale token does.
    second = _delete(client, auth["headers"])
    assert second.status_code == 401


# --- cascade ----------------------------------------------------------------------


def test_delete_account_removes_owner_scoped_database_rows(client, tmp_path: Path):
    auth = register_user(client, "alice@example.com")
    headers = auth["headers"]
    user_id = auth["user"]["id"]

    repo_dir = tmp_path / "storage" / "repositories" / "repo-1"
    repo_dir.mkdir(parents=True)
    (repo_dir / "marker.txt").write_text("hello")

    from app.core.database import SessionLocal
    from app.models.ai_conversation import AiConversationMessageRecord
    from app.models.ai_provider_config import AiProviderConfigRecord
    from app.models.refresh_token import RefreshToken
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        db.add(
            RepositoryRecord(
                id="repo-1",
                owner_id=user_id,
                name="alice-repo",
                source="upload",
                local_path=str(repo_dir),
                status="completed",
            )
        )
        db.commit()

        db.add(
            AiProviderConfigRecord(
                id="cfg-1",
                owner_id=user_id,
                provider="openai",
                encrypted_api_key="ciphertext",
                api_key_last4="abcd",
            )
        )
        db.add(
            AiConversationMessageRecord(
                id="msg-1",
                owner_id=user_id,
                repository_id="repo-1",
                sequence=0,
                role="user",
                content="hello",
            )
        )
        db.commit()
    finally:
        db.close()

    assert repo_dir.exists()

    response = _delete(client, headers)
    assert response.status_code == 204

    db = SessionLocal()
    try:
        from app.models.account_deletion_audit import AccountDeletionAuditRecord
        from app.models.user import User

        assert db.get(User, user_id) is None
        assert db.query(RepositoryRecord).filter_by(owner_id=user_id).count() == 0
        assert db.query(AiProviderConfigRecord).filter_by(owner_id=user_id).count() == 0
        assert db.query(AiConversationMessageRecord).filter_by(owner_id=user_id).count() == 0
        assert db.query(RefreshToken).filter_by(user_id=user_id).count() == 0

        audits = db.query(AccountDeletionAuditRecord).filter_by(deleted_user_id=user_id).all()
        assert len(audits) == 1
        assert audits[0].status == "completed"
        assert audits[0].completed_at is not None
    finally:
        db.close()

    # Storage cleanup ran too: the repository's on-disk directory is gone.
    assert not repo_dir.exists()


def test_delete_account_does_not_affect_other_owners(client):
    alice = register_user(client, "alice@example.com")
    bob = register_user(client, "bob@example.com")

    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        db.add(
            RepositoryRecord(
                id="bob-repo",
                owner_id=bob["user"]["id"],
                name="bob-repo",
                source="upload",
                local_path="/tmp/bob-repo-does-not-exist",
                status="completed",
            )
        )
        db.commit()
    finally:
        db.close()

    assert _delete(client, alice["headers"]).status_code == 204

    # Bob is untouched: still authenticated, still owns his repository.
    assert client.get("/auth/me", headers=bob["headers"]).status_code == 200
    listing = client.get("/repositories", headers=bob["headers"])
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


# --- seed user guard (service-level: unreachable via HTTP) ----------------------


def test_seed_user_cannot_be_deleted():
    from app.core.exceptions import ValidationServiceError
    from app.models.user import SEED_USER_ID, SEED_USER_EMAIL, User
    from app.services.account_deletion_service import AccountDeletionService

    seed_user = User(id=SEED_USER_ID, email=SEED_USER_EMAIL, password_hash=None)
    service = AccountDeletionService(db=None, repository=None, storage=None)  # type: ignore[arg-type]

    import pytest

    with pytest.raises(ValidationServiceError):
        service.delete_account(seed_user, password="irrelevant", confirm_email=SEED_USER_EMAIL)
