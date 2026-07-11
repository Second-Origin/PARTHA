import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import MemoryRateLimitStore, StoreUnavailableError, classify

RATE_ENV = {
    "RATE_LIMIT_DEFAULT_PER_MINUTE": "3",
    "RATE_LIMIT_HEAVY_PER_MINUTE": "2",
    "RATE_LIMIT_AI_PER_MINUTE": "2",
}


@pytest.fixture()
def limited_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """The standard client fixture with budgets small enough to exhaust."""
    database_path = tmp_path / "partha-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    for key, value in RATE_ENV.items():
        monkeypatch.setenv(key, value)

    from app.core import config

    config.get_settings.cache_clear()

    import app.core.database as database

    settings = config.get_settings()
    database.settings = settings
    database.engine.dispose()
    database.connect_args = {"check_same_thread": False}
    database.engine = database.create_engine(settings.database_url, pool_pre_ping=True, connect_args=database.connect_args)
    database.SessionLocal.configure(bind=database.engine)

    from app.main import create_app
    from app.models.base import Base

    Base.metadata.create_all(bind=database.engine)
    with TestClient(create_app()) as test_client:
        yield test_client

    for key in ("DATABASE_URL", "STORAGE_PATH", "AUTO_CREATE_TABLES", "CORS_ORIGINS", *RATE_ENV):
        os.environ.pop(key, None)
    config.get_settings.cache_clear()


# --- classifier ----------------------------------------------------------------


def test_classify_maps_routes_to_budget_classes():
    assert classify("POST", "/auth/login") == "auth"
    assert classify("POST", "/auth/register") == "auth"
    assert classify("POST", "/ai/query") == "ai"
    assert classify("GET", "/ai/config") == "ai"
    assert classify("POST", "/repositories/upload") == "heavy"
    assert classify("POST", "/repositories/github") == "heavy"
    assert classify("POST", "/analysis/some-id/start") == "heavy"
    assert classify("GET", "/analysis/some-id/status") == "default"
    assert classify("POST", "/documentation/generate") == "heavy"
    assert classify("POST", "/reports/export") == "heavy"
    assert classify("GET", "/repositories") == "default"
    # Exemptions: probes, docs, and CORS preflight.
    assert classify("GET", "/health") is None
    assert classify("GET", "/metrics") is None
    assert classify("GET", "/docs") is None
    assert classify("OPTIONS", "/repositories") is None


# --- memory store --------------------------------------------------------------


def test_memory_store_counts_and_resets_after_window():
    now = [1000.0]
    store = MemoryRateLimitStore(clock=lambda: now[0])

    counts = [store.hit("k", 60)[0] for _ in range(3)]
    assert counts == [1, 2, 3]

    _, retry_after = store.hit("k", 60)
    assert 1 <= retry_after <= 60

    now[0] += 61  # past the window: the counter starts over
    count, _ = store.hit("k", 60)
    assert count == 1


def test_memory_store_keys_are_independent():
    store = MemoryRateLimitStore(clock=lambda: 0.0)
    assert store.hit("a", 60)[0] == 1
    assert store.hit("b", 60)[0] == 1


# --- middleware behaviour -------------------------------------------------------


def test_exceeding_default_budget_returns_429_with_retry_after(limited_client):
    for _ in range(3):
        assert limited_client.get("/repositories").status_code == 200

    blocked = limited_client.get("/repositories")
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["code"] == "rate_limited"
    assert body["details"]["retryAfterSeconds"] >= 1
    assert int(blocked.headers["Retry-After"]) >= 1


def test_budget_classes_are_charged_separately(limited_client):
    # Exhaust the heavy budget (2/min) with invalid imports — the limiter runs
    # before validation, so 422s are charged too.
    assert limited_client.post("/repositories/github", json={}).status_code != 429
    assert limited_client.post("/repositories/github", json={}).status_code != 429
    assert limited_client.post("/repositories/github", json={}).status_code == 429

    # The default class still has budget left.
    assert limited_client.get("/repositories").status_code == 200


def test_probes_are_never_limited(limited_client):
    for _ in range(10):
        assert limited_client.get("/health").status_code == 200


def test_cors_preflight_is_never_limited(limited_client):
    for _ in range(3):
        limited_client.get("/repositories")  # exhaust the default budget

    preflight = limited_client.options(
        "/repositories",
        headers={"Origin": "http://testserver", "Access-Control-Request-Method": "GET"},
    )
    assert preflight.status_code == 200


def test_store_failure_fails_open_loudly(limited_client):
    class FailingStore:
        def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
            raise StoreUnavailableError("redis is down")

    from app.core.observability import runtime_metrics

    degraded_before = runtime_metrics.rate_limit_degraded_total
    limited_client.app.state.rate_limit_store = FailingStore()

    # Way past the budget, yet everything is served — and counted as degraded.
    for _ in range(5):
        assert limited_client.get("/repositories").status_code == 200
    assert runtime_metrics.rate_limit_degraded_total >= degraded_before + 5


def test_metrics_endpoint_exposes_rate_limit_counters(limited_client):
    text = limited_client.get("/metrics").text
    assert "partha_rate_limited_requests_total" in text
    assert "partha_rate_limit_degraded_total" in text
