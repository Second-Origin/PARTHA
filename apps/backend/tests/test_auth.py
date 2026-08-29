import uuid

import pytest

from tests.api_assertions import assert_error_response
from tests.conftest import approve_email

REGISTER = {"email": "alice@example.com", "password": "correct-horse-battery"}
COOKIE = "partha_refresh"


def _register(client, email="alice@example.com", password="correct-horse-battery", skip_approval=False):
    if not skip_approval:
        approve_email(email, f"test:{email}")
    return client.post("/auth/register", json={"email": email, "password": password})


def _current_refresh_cookie(client) -> str | None:
    return client.cookies.get(COOKIE)


def _refresh_with(client, raw: str):
    """Call /auth/refresh presenting exactly this token, bypassing the jar.

    The jar is cleared first because httpx would otherwise merge its own
    (rotated) cookie into the request alongside the explicit header.
    """
    client.cookies.clear()
    return client.post("/auth/refresh", headers={"Cookie": f"{COOKIE}={raw}"})


# --- register -----------------------------------------------------------------


def test_register_returns_token_and_sets_refresh_cookie(client):
    response = _register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert body["accessToken"]
    assert body["user"]["email"] == "alice@example.com"

    set_cookie = response.headers["set-cookie"]
    assert COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()


def test_register_duplicate_email_conflicts(client):
    assert _register(client).status_code == 201

    duplicate = _register(client)
    assert_error_response(duplicate, 409, "conflict_error")


def test_register_rejects_short_password(client):
    response = _register(client, password="short")
    error = assert_error_response(response, 422, "request_validation_error")
    assert error.details is not None
    assert "errors" in error.details


def test_register_with_an_approved_email_succeeds(client):
    """Baseline: a pre-approved email lets registration through (#374)."""
    approve_email("alice@example.com")

    response = _register(client, skip_approval=True)

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "alice@example.com"


def test_register_rejects_an_email_that_was_never_approved(client):
    response = _register(client, skip_approval=True)

    error = assert_error_response(response, 422, "validation_error")
    assert "hasn't been approved" in error.message
    assert "waitlist" in error.message.lower()


def test_register_still_succeeds_after_the_approved_email_is_used_once(client):
    """Approval is not single-use (#374): re-registering the SAME email a
    second time is rejected by the ordinary email-uniqueness conflict, not
    by the allowlist itself -- and a genuinely different, still-unused
    approval for a different email is completely unaffected by the first
    registration."""
    approve_email("shared-approval@example.com")
    first = client.post(
        "/auth/register", json={"email": "shared-approval@example.com", "password": "correct-horse-battery"}
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/auth/register", json={"email": "shared-approval@example.com", "password": "another-password-entirely"}
    )
    assert_error_response(duplicate, 409, "conflict_error")

    from app.core.database import SessionLocal
    from app.models.approved_email import ApprovedEmail
    from sqlalchemy import select

    with SessionLocal() as db:
        approval = db.scalars(select(ApprovedEmail).where(ApprovedEmail.email == "shared-approval@example.com")).one()
        assert approval.used_at is not None
        assert approval.used_by_user_id == first.json()["user"]["id"]


def test_register_commit_time_collision_is_reported_as_conflict(client, monkeypatch):
    """Two concurrent registrations for the same email can both pass the
    existence check before either writes; the unique constraint is the real
    guard, and its IntegrityError must be turned into the same 409 the normal
    duplicate path returns - never a 500, and the session must stay usable.

    Deterministic by construction: rather than racing real threads (which
    would need a production-code hook to land the interleaving reliably), the
    "losing" session's own `flush()` is intercepted to run a second,
    completely independent session's successful registration first - the
    exact database-level interleaving a real race produces - before the
    original flush proceeds and collides on the unique email constraint.
    Intercepting flush rather than commit: register() flushes the new user
    row before commit (so `user.id` exists to stamp onto the approval's
    `used_by_user_id`), so that flush is where the loser's write lock is
    actually acquired and where the collision actually surfaces --
    intercepting commit instead would have the loser already holding that
    lock when the "concurrent" winner tries to write, deadlocking the single
    test process against itself rather than reproducing the race.
    """
    from sqlalchemy import select

    from app.auth.service import AuthService
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.core.exceptions import ConflictServiceError
    from app.models.user import User

    winner_email = "Racer@Example.com"
    loser_email = "  racer@EXAMPLE.com  "  # mixed case + whitespace: same normalized address
    normalized = "racer@example.com"
    settings = get_settings()

    # One approval covers both attempts: it's the same normalized address,
    # and approval isn't consumed by use (#374) -- only the email-uniqueness
    # constraint this test is actually about does that job.
    approve_email(normalized)

    loser_session = SessionLocal()
    try:
        loser_service = AuthService(loser_session, settings)

        # The loser's own existence check, run here before the winner exists,
        # is exactly what a real concurrent request would see: nothing yet.
        assert loser_session.scalars(select(User).where(User.email == normalized)).first() is None

        original_flush = loser_session.flush

        def flush_after_concurrent_winner_lands(*args, **kwargs):
            winner_session = SessionLocal()
            try:
                AuthService(winner_session, settings).register(winner_email, "correct-horse-battery")
            finally:
                winner_session.close()
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(loser_session, "flush", flush_after_concurrent_winner_lands)

        with pytest.raises(ConflictServiceError) as exc_info:
            loser_service.register(loser_email, "another-password-entirely")
        assert exc_info.value.message == "An account with this email already exists."
        assert exc_info.value.status_code == 409

        # The session is usable after the rollback: a fresh query on it works
        # and sees the winner's row (not the loser's, which never committed).
        after_rollback = loser_session.scalars(select(User).where(User.email == normalized)).one()
        assert after_rollback.email == normalized
    finally:
        loser_session.close()

    # Exactly one user for the normalized email, confirmed from a clean session.
    verify_session = SessionLocal()
    try:
        matches = verify_session.scalars(select(User).where(User.email == normalized)).all()
        assert len(matches) == 1
    finally:
        verify_session.close()


# --- login --------------------------------------------------------------------


def test_login_works_and_normalizes_email_case(client):
    _register(client)

    response = client.post("/auth/login", json={"email": "ALICE@Example.COM", "password": REGISTER["password"]})
    assert response.status_code == 200
    token = response.json()["accessToken"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_wrong_password_and_unknown_email_are_indistinguishable(client):
    _register(client)

    wrong_password = client.post("/auth/login", json={"email": REGISTER["email"], "password": "not-the-password"})
    unknown_email = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever-here"})

    wrong_error = assert_error_response(wrong_password, 401, "unauthorized")
    unknown_error = assert_error_response(unknown_email, 401, "unauthorized")
    assert wrong_error.model_dump(exclude={"request_id"}) == unknown_error.model_dump(exclude={"request_id"})


def test_user_without_credential_cannot_login(client):
    # Rows created outside registration (the seed user, pre-auth dev users)
    # have password_hash NULL; login against them must fail like any bad
    # credential rather than crashing or succeeding.
    from app.core.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        db.add(User(id=str(uuid.uuid4()), email="legacy@example.com", password_hash=None))
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/login", json={"email": "legacy@example.com", "password": "anything-at-all"})
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


# --- access tokens ------------------------------------------------------------


def test_me_requires_a_token(client):
    assert_error_response(client.get("/auth/me"), 401, "unauthorized")


def test_me_rejects_garbage_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_expired_access_token_is_rejected(client):
    user_id = _register(client).json()["user"]["id"]

    from app.auth.security import create_access_token
    from app.core.config import get_settings

    expired = create_access_token(user_id, get_settings(), ttl_seconds=-10)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


# --- refresh rotation ---------------------------------------------------------


def test_refresh_rotates_and_new_token_works(client):
    _register(client)
    first_cookie = _current_refresh_cookie(client)

    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    second_cookie = _current_refresh_cookie(client)
    assert second_cookie and second_cookie != first_cookie

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {refreshed.json()['accessToken']}"})
    assert me.status_code == 200


def test_refresh_reuse_revokes_the_whole_family(client):
    _register(client)
    stolen = _current_refresh_cookie(client)

    assert client.post("/auth/refresh").status_code == 200
    successor = _current_refresh_cookie(client)

    # Replaying the rotated (stolen) token fails...
    assert _refresh_with(client, stolen).status_code == 401

    # ...and takes the legitimate successor down with it.
    assert _refresh_with(client, successor).status_code == 401


def test_refresh_without_cookie_is_unauthorized(client):
    assert_error_response(client.post("/auth/refresh"), 401, "unauthorized")


def test_logout_revokes_and_is_idempotent(client):
    _register(client)
    cookie_before = _current_refresh_cookie(client)

    assert client.post("/auth/logout").status_code == 204

    assert _refresh_with(client, cookie_before).status_code == 401
    assert client.post("/auth/logout").status_code == 204


def test_logout_rate_limit_error_uses_the_standard_envelope(client, monkeypatch):
    # Logout is a public, idempotent route. Set its real middleware budget to
    # zero so the first ASGI request deterministically exercises its documented
    # 429 response without changing the route or relying on timing.
    settings = client.app.state.rate_limit_settings
    monkeypatch.setattr(
        client.app.state,
        "rate_limit_settings",
        settings.model_copy(update={"rate_limit_default_per_minute": 0}),
    )

    response = client.post("/auth/logout")

    error = assert_error_response(response, 429, "rate_limited")
    assert error.details is not None
    assert error.details["retryAfterSeconds"] >= 1
    assert int(response.headers["Retry-After"]) >= 1


# --- storage hygiene ----------------------------------------------------------


def test_no_plaintext_credentials_or_raw_tokens_in_database(client):
    _register(client)
    raw_refresh = _current_refresh_cookie(client)

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.refresh_token import RefreshToken
    from app.models.user import User

    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == REGISTER["email"])).one()
        assert user.password_hash.startswith("$argon2id$")
        assert REGISTER["password"] not in user.password_hash

        hashes = db.scalars(select(RefreshToken.token_hash)).all()
        assert hashes, "expected at least one refresh token row"
        assert raw_refresh not in hashes
        assert all(len(value) == 64 for value in hashes)  # sha256 hex, never the raw token
    finally:
        db.close()


# --- signing-secret strength --------------------------------------------------


def test_auth_secret_key_is_required_and_strong_outside_dev():
    from pydantic import ValidationError

    from app.core.config import Settings

    # Production also requires an AI encryption key; supply a valid one so this
    # test isolates the auth-secret behaviour rather than tripping that check.
    from cryptography.fernet import Fernet

    ai_key = Fernet.generate_key().decode()

    # Non-dev refuses to start without a secret...
    with pytest.raises(ValidationError):
        Settings(app_env="production", ai_encryption_key=ai_key)
    # ...and with a weak one.
    with pytest.raises(ValidationError):
        Settings(app_env="production", auth_secret_key="too-short", ai_encryption_key=ai_key)
    # A sufficiently long secret is accepted.
    strong = "s" * 32
    assert Settings(app_env="production", auth_secret_key=strong, ai_encryption_key=ai_key).auth_secret_key == strong
    # Development stays lenient: an empty secret resolves to the dev default.
    assert Settings(app_env="development", auth_secret_key="").auth_secret_key


# --- interaction with protected routes ----------------------------------------


def test_bearer_token_attributes_repository_routes_to_that_user(client):
    token = _register(client).json()["accessToken"]
    user_id = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        db.add(
            RepositoryRecord(
                id=str(uuid.uuid4()),
                owner_id=user_id,
                name="alice-repo",
                source="upload",
                local_path="/tmp/alice-repo",
                status="completed",
            )
        )
        db.commit()
    finally:
        db.close()

    with_token = client.get("/repositories", headers={"Authorization": f"Bearer {token}"})
    assert with_token.status_code == 200
    assert with_token.json()["total"] == 1


def test_invalid_bearer_on_protected_routes_is_rejected(client):
    # Presenting a bad token is an authentication attempt; it must never fall
    # back to any anonymous or seed identity.
    response = client.get("/repositories", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_anonymous_repository_access_is_rejected(client):
    # E1.3 (#63) removed the pre-auth fallback: protected routes now require a
    # valid token, so an anonymous request is unauthorized rather than served
    # an empty seed-user view.
    response = client.get("/repositories")
    assert response.status_code == 401
