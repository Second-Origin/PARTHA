import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import UnauthorizedError

PG_URL = os.environ.get("PARTHA_TEST_PG_URL")


def _make_refresh_token(db, user_id: str, family_id: str | None = None) -> str:
    from app.auth.security import hash_refresh_token, new_refresh_token
    from app.models.refresh_token import RefreshToken

    raw = new_refresh_token()
    db.add(
        RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id or str(uuid.uuid4()),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    db.commit()
    return raw


def test_claim_token_is_single_use(client):
    """The atomic claim lets exactly one caller mark a token used.

    This is the primitive the whole rotation race depends on: two requests can
    both read used_at IS NULL, but only one UPDATE can affect the row. Proven
    deterministically here (sequential) on whatever engine the suite runs.
    """
    from app.auth.service import AuthService
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.models.refresh_token import RefreshToken
    from app.models.user import User

    db = SessionLocal()
    try:
        user = User(id=str(uuid.uuid4()), email="claim@example.com")
        db.add(user)
        db.commit()
        _make_refresh_token(db, user.id)
        token_id = db.query(RefreshToken).one().id

        service = AuthService(db, get_settings())
        now = datetime.now(UTC)
        assert service._claim_token(token_id, now) is True  # the winner
        assert service._claim_token(token_id, now) is False  # WHERE used_at IS NULL rejects the rest
    finally:
        db.close()


def test_refresh_loser_revokes_family_making_winners_successor_unusable(client):
    """Deterministic companion to the real-Postgres test below: proves the
    *service-level rule* that a lost claim revokes the whole family - including
    the legitimate successor the winner just received - without needing
    threads or a real row lock. This is strict fail-closed replay protection
    by design (see Finding B in the PR description): any concurrent
    presentation of the same refresh token is treated as possible theft, so
    the winner is deliberately logged out too rather than silently kept alive.
    """
    from sqlalchemy import select

    from app.auth.security import hash_refresh_token
    from app.auth.service import AuthService
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.models.refresh_token import RefreshToken

    from tests.conftest import issue_invite_code

    settings = get_settings()
    register = client.post(
        "/auth/register",
        json={
            "email": "family-revoke@example.com",
            "password": "correct-horse-battery",
            "inviteCode": issue_invite_code("test:family-revoke"),
        },
    )
    raw = register.cookies.get("partha_refresh")

    db = SessionLocal()
    try:
        service = AuthService(db, settings)
        _, _, successor = service.refresh(raw)

        # A second presentation of the now-used token is exactly what a losing
        # concurrent request sees: reuse -> the whole family is revoked.
        with pytest.raises(UnauthorizedError):
            service.refresh(raw)

        # The winner's own successor is now unusable too - proving the rule,
        # not just that *a* rejection happened.
        with pytest.raises(UnauthorizedError):
            service.refresh(successor)

        original = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))).one()
        family_rows = db.scalars(select(RefreshToken).where(RefreshToken.family_id == original.family_id)).all()
        assert len(family_rows) >= 2, "expected at least the original token and its successor"
        assert all(row.revoked_at is not None for row in family_rows), "every row in the family must be revoked"
        assert not any(row.used_at is None and row.revoked_at is None for row in family_rows), (
            "no unused, unrevoked token should remain in the family"
        )
    finally:
        db.close()


@pytest.mark.skipif(not PG_URL, reason="set PARTHA_TEST_PG_URL to run the Postgres concurrency test")
def test_concurrent_refresh_on_postgres_mints_one_successor():
    """Two threads refreshing the same token against a real Postgres: exactly
    one wins. The loser blocks on the row lock, sees the used_at guard fail, and
    is rejected — SQLite serializes writes and cannot exercise this.

    Beyond just "one ok, one rejected", this also proves the *final* state:
    the winner's successor is captured and then, from a fresh session after
    both threads finish, shown to be unusable, and every row in the family is
    confirmed revoked - so a real concurrent claim loss is proven to revoke
    the family for real, not just in the deterministic companion test above.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.auth.service import AuthService
    from app.core.config import Settings
    from app.models.base import Base
    from app.models.refresh_token import RefreshToken
    from app.models.user import User

    engine = create_engine(PG_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(app_env="test")

    setup = Session()
    try:
        user = User(id=str(uuid.uuid4()), email=f"pg-{uuid.uuid4().hex}@example.com")
        setup.add(user)
        setup.commit()
        raw = _make_refresh_token(setup, user.id)
        user_id = user.id
        family_id = setup.query(RefreshToken).filter(RefreshToken.user_id == user_id).one().family_id
    finally:
        setup.close()

    results: list[str] = []
    winner_successors: list[str] = []
    results_lock = threading.Lock()
    start = threading.Barrier(2)

    def worker() -> None:
        session = Session()
        outcome = "error"
        try:
            start.wait(timeout=10)
            _, _, successor = AuthService(session, settings).refresh(raw)
            outcome = "ok"
            with results_lock:
                winner_successors.append(successor)
        except UnauthorizedError:
            outcome = "rejected"
        finally:
            session.close()
            with results_lock:
                results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    stuck = [thread for thread in threads if thread.is_alive()]

    try:
        # A stuck thread or an unexpected exception (outcome left as "error")
        # must fail the test loudly, never be read as an expected rejection.
        assert not stuck, f"{len(stuck)} worker thread(s) did not finish within the timeout"
        assert sorted(results) == ["ok", "rejected"], results
        assert len(winner_successors) == 1, "exactly one thread should have minted a successor"

        verify = Session()
        try:
            with pytest.raises(UnauthorizedError):
                AuthService(verify, settings).refresh(winner_successors[0])

            family_rows = verify.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
            assert len(family_rows) >= 2, "expected at least the original token and the winner's successor"
            assert all(row.revoked_at is not None for row in family_rows), (
                "every row in the family must be revoked after a real concurrent replay"
            )
            assert not any(row.used_at is None and row.revoked_at is None for row in family_rows), (
                "no second usable successor should remain in the family"
            )
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
