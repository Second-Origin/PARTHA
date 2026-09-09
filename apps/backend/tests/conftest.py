import os
from collections.abc import Callable, Generator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

DEFAULT_TEST_PASSWORD = "correct-horse-battery-staple"


def approve_email(email: str, note: str | None = None) -> None:
    """Insert an ApprovedEmail row directly (#374) -- registration requires
    the address to be on the allowlist, and tests need a real approval the
    same way an operator running scripts/approve_email.py would produce one,
    not a bypass around the check. A no-op if already approved, mirroring
    the script's own idempotence.
    """
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.approved_email import ApprovedEmail

    normalized = email.strip().lower()
    with SessionLocal() as session:
        existing = session.scalars(select(ApprovedEmail).where(ApprovedEmail.email == normalized)).first()
        if existing is not None:
            return
        session.add(ApprovedEmail(id=str(uuid4()), email=normalized, note=note))
        session.commit()


def register_user(
    client: TestClient,
    email: str,
    password: str = DEFAULT_TEST_PASSWORD,
) -> dict:
    """Register a user through the real endpoint and return an auth bundle.

    Returns a dict with ``token`` (access token), ``user`` (the user payload)
    and ``headers`` (a ready-to-use ``Authorization`` header), so tests can
    exercise the owner-scoped routes as a genuine authenticated caller rather
    than relying on any pre-auth fallback (removed in E1.3 / #63). Approves
    the email first so every call site keeps working unchanged; a test
    exercising allowlist behavior itself calls the real endpoint directly.
    """
    approve_email(email, note=f"test:{email}")
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    token = body["accessToken"]
    return {"token": token, "user": body["user"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(autouse=True)
def _no_frontend_dist_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test gets a FRONTEND_DIST_PATH guaranteed not to exist (#339),
    regardless of which fixture (or none) it uses to build the app.

    Without this, the default relative frontend_dist_path resolves against
    whatever the process's actual cwd is, so a developer who happens to have
    a real apps/frontend/dist built locally would get different backend
    test behavior than someone who doesn't -- and CI, which never builds the
    frontend, than either of them. A test that specifically wants the SPA
    mount (see test_frontend_hosting.py) overrides this after depending on
    it, same as any other monkeypatch.setenv call.
    """
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend-dist-here"))


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "partha-test.db"
    storage_path = tmp_path / "storage"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_PATH", str(storage_path))
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    # Deliberately "test", not the default "development": AuthService's
    # dev-only allowlist bypass (#384) is scoped to app_env == "development"
    # specifically so it never applies to the test suite -- without this,
    # every test asserting an allowlist rejection would silently start
    # passing for the wrong reason (auto-approval, not a real check).
    monkeypatch.setenv("APP_ENV", "test")
    # Tests drive AnalysisWorker.run_once() deterministically; the background
    # daemon thread would otherwise race the queue non-deterministically (#93).
    monkeypatch.setenv("ANALYSIS_WORKER_AUTOSTART", "false")

    from app.core import config

    config.get_settings.cache_clear()

    import app.core.database as database

    settings = config.get_settings()
    database.settings = settings
    database.engine.dispose()
    database.connect_args = {"check_same_thread": False}
    database.engine = database.create_engine(
        settings.database_url, pool_pre_ping=True, connect_args=database.connect_args
    )
    database.SessionLocal.configure(bind=database.engine)

    from app.core.schema_sync import stamp_head
    from app.main import create_app
    from app.models.base import Base

    Base.metadata.create_all(bind=database.engine)
    # Mirrors what the app's own lifespan does for a genuinely fresh database
    # (#166): without this, the lifespan's schema-drift check sees an
    # unstamped database with every table already present and misreads it as
    # drift instead of a fresh test database.
    stamp_head(database.engine)
    with TestClient(create_app()) as test_client:
        yield test_client

    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("STORAGE_PATH", None)
    os.environ.pop("AUTO_CREATE_TABLES", None)
    os.environ.pop("CORS_ORIGINS", None)
    os.environ.pop("ANALYSIS_WORKER_AUTOSTART", None)
    config.get_settings.cache_clear()


@pytest.fixture()
def auth_client(client: TestClient) -> TestClient:
    """A ``client`` pre-authenticated as a real registered user.

    A registered user's access token is attached as a default header, so every
    request the test makes is authenticated and owner-scoped to that user — the
    same posture the frontend has after sign-in. ``client.default_user`` exposes
    the user payload for tests that need the id or email.
    """
    auth = register_user(client, "primary@example.com")
    client.headers.update(auth["headers"])
    client.default_user = auth["user"]  # type: ignore[attr-defined]
    return client


@pytest.fixture()
def make_auth_headers(client: TestClient) -> Callable[[str], dict]:
    """Factory that registers an additional user and returns their auth bundle.

    Lets a single test act as two distinct owners behind the same client IP,
    which is exactly what the cross-owner and per-user rate-limit tests need.
    """

    def _make(email: str) -> dict:
        return register_user(client, email)

    return _make
