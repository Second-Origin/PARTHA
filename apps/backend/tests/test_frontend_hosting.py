"""Single-service frontend hosting (#339): app.main mounts a built frontend
when one is present, and behaves exactly as before when one is not."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _write_fake_build(dist_path: Path) -> None:
    dist_path.mkdir(parents=True, exist_ok=True)
    (dist_path / "index.html").write_text("<html><body>spa shell</body></html>", encoding="utf-8")
    assets_path = dist_path / "assets"
    assets_path.mkdir(parents=True, exist_ok=True)
    (assets_path / "app.js").write_text("console.log('app');", encoding="utf-8")


@pytest.fixture()
def mounted_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Same boot as the shared `client` fixture, except FRONTEND_DIST_PATH
    points at a real, populated build directory instead of a missing one."""

    dist_path = tmp_path / "dist"
    _write_fake_build(dist_path)

    database_path = tmp_path / "partha-test.db"
    storage_path = tmp_path / "storage"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_PATH", str(storage_path))
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    monkeypatch.setenv("ANALYSIS_WORKER_AUTOSTART", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(dist_path))

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
    stamp_head(database.engine)
    with TestClient(create_app()) as test_client:
        yield test_client


def test_no_dist_directory_leaves_unmatched_routes_404ing(client: TestClient) -> None:
    # The shared `client` fixture points FRONTEND_DIST_PATH at a directory
    # that does not exist, matching a plain local-dev boot with no built
    # frontend. Nothing should be mounted, and an arbitrary client-side
    # route stays a normal 404 instead of silently becoming a 200.
    response = client.get("/dashboard")
    assert response.status_code == 404


def test_health_route_is_never_shadowed_by_a_mounted_frontend(mounted_client: TestClient) -> None:
    response = mounted_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_client_side_route_and_direct_refresh_both_get_the_spa_shell(mounted_client: TestClient) -> None:
    root = mounted_client.get("/")
    deep_link = mounted_client.get("/dashboard/some/nested/route")

    assert root.status_code == 200
    assert "spa shell" in root.text
    assert deep_link.status_code == 200
    assert "spa shell" in deep_link.text


def test_built_asset_is_served_directly(mounted_client: TestClient) -> None:
    response = mounted_client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text
