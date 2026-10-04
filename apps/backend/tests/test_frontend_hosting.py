"""Single-service frontend hosting (#339): app.main mounts a built frontend
when one is present, and behaves exactly as before when one is not."""

import base64
from collections.abc import Generator
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


INLINE_SCRIPT = "document.documentElement.dataset.boot = 'ok';"


def _write_fake_build(dist_path: Path) -> None:
    dist_path.mkdir(parents=True, exist_ok=True)
    (dist_path / "index.html").write_text(
        f"<html><head><script>{INLINE_SCRIPT}</script></head><body>spa shell</body></html>", encoding="utf-8"
    )
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


@pytest.mark.parametrize(
    "traversal_path",
    [
        "/../secret.txt",
        "/assets/../../secret.txt",
        "/%2e%2e/secret.txt",
        "/..%2fsecret.txt",
    ],
)
def test_traversal_attempts_cannot_escape_the_dist_directory(
    mounted_client: TestClient, tmp_path: Path, traversal_path: str
) -> None:
    # A file that sits next to (not inside) the mounted dist directory must
    # never be reachable through the catch-all handler, no matter how the
    # ".." segments are spelled in the request path.
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")

    response = mounted_client.get(traversal_path)

    assert response.status_code == 200
    assert "top secret" not in response.text
    assert "spa shell" in response.text


def test_spa_shell_gets_a_policy_that_lets_the_page_load(mounted_client: TestClient) -> None:
    # The API's deny-all CSP on the shell blanked the whole page in the
    # single-service image: every script and stylesheet was blocked.
    csp = mounted_client.get("/dashboard").headers["Content-Security-Policy"]
    inline_hash = base64.b64encode(hashlib.sha256(INLINE_SCRIPT.encode("utf-8")).digest()).decode()

    assert "default-src 'none'" not in csp
    assert "script-src 'self'" in csp
    assert f"'sha256-{inline_hash}'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_api_routes_keep_the_deny_all_policy_when_the_frontend_is_mounted(mounted_client: TestClient) -> None:
    response = mounted_client.get("/health")

    assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")


@pytest.mark.parametrize("path", ["/repositories", "/repositories/some-id", "/analysis/some-id/architecture"])
def test_page_load_on_a_path_the_api_shares_gets_the_spa_shell(mounted_client: TestClient, path: str) -> None:
    # These client-side routes are also API paths. Refreshing one of them
    # returned the API's 401 JSON instead of the app.
    response = mounted_client.get(path, headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})

    assert response.status_code == 200
    assert "spa shell" in response.text
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"


def test_api_fetch_on_a_shared_path_still_reaches_the_api(mounted_client: TestClient) -> None:
    response = mounted_client.get("/repositories", headers={"Accept": "application/json"})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


@pytest.mark.parametrize("path", ["/docs", "/health", "/auth/oauth/github/callback"])
def test_page_load_on_a_browser_facing_api_path_is_left_to_the_api(mounted_client: TestClient, path: str) -> None:
    response = mounted_client.get(path, headers={"Accept": "text/html"})

    assert "spa shell" not in response.text
