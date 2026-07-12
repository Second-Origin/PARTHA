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


@pytest.mark.skipif(not PG_URL, reason="set PARTHA_TEST_PG_URL to run the Postgres concurrency test")
def test_concurrent_refresh_on_postgres_mints_one_successor():
    """Two threads refreshing the same token against a real Postgres: exactly
    one wins. The loser blocks on the row lock, sees the used_at guard fail, and
    is rejected — SQLite serializes writes and cannot exercise this."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.auth.service import AuthService
    from app.core.config import Settings
    from app.models.base import Base
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
    finally:
        setup.close()

    results: list[str] = []
    results_lock = threading.Lock()
    start = threading.Barrier(2)

    def worker() -> None:
        session = Session()
        outcome = "error"
        try:
            start.wait(timeout=10)
            AuthService(session, settings).refresh(raw)
            outcome = "ok"
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

    try:
        assert sorted(results) == ["ok", "rejected"], results
    finally:
        cleanup = Session()
        try:
            from app.models.refresh_token import RefreshToken

            cleanup.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
