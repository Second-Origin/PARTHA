import asyncio
import io
import os
import uuid
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import MemoryRateLimitStore, StoreUnavailableError, classify
from tests.conftest import register_user

REDIS_URL = os.environ.get("PARTHA_TEST_REDIS_URL")


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    """Minimal stand-in for a Starlette Request for resolve_rate_key.

    resolve_rate_key only reads ``.headers.get('authorization')`` and
    ``.client.host``; a dict of lowercased headers matches Starlette's
    case-insensitive lookup for these tests.
    """

    def __init__(self, headers: dict[str, str], host: str = "203.0.113.9") -> None:
        self.headers = headers
        self.client = _FakeClient(host)


def _hit(store, key: str, window: int) -> tuple[int, int]:
    """Drive the async store.hit from a synchronous test."""
    return asyncio.run(store.hit(key, window))


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _import_sample(client) -> str:
    response = client.post(
        "/repositories/upload",
        files={
            "file": (
                "sample.zip",
                _zip_bytes({"sample/package.json": '{"dependencies":{}}'}),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 201
    return response.json()["id"]

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

    from app.core.schema_sync import stamp_head
    from app.main import create_app
    from app.models.base import Base

    Base.metadata.create_all(bind=database.engine)
    # Mirrors what the app's own lifespan does for a genuinely fresh database
    # (#166); see the identical comment in tests/conftest.py.
    stamp_head(database.engine)
    with TestClient(create_app()) as test_client:
        # Protected routes now require auth (E1.3 / #63); authenticate as a real
        # user so the budget tests exercise the routes rather than bouncing off
        # a 401. Requests are keyed on this user's id — the register call below
        # is the "auth" class, which the small RATE_ENV budgets do not touch.
        auth = register_user(test_client, "limited@example.com")
        test_client.headers.update(auth["headers"])
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
    assert classify("POST", "/export") == "heavy"
    assert classify("GET", "/repositories") == "default"
    # Exemptions: probes, docs, and CORS preflight.
    assert classify("GET", "/health") is None
    assert classify("GET", "/metrics") is None
    assert classify("GET", "/docs") is None
    assert classify("OPTIONS", "/repositories") is None


# --- identity resolution (per-user vs client IP) --------------------------------


def _test_settings():
    from app.core.config import Settings

    return Settings(app_env="test")


def test_resolve_rate_key_uses_validated_user_id_for_authenticated_requests():
    from app.auth.security import create_access_token
    from app.core.rate_limit import resolve_rate_key

    settings = _test_settings()
    token = create_access_token("user-123", settings)
    request = _FakeRequest({"authorization": f"Bearer {token}"})

    assert resolve_rate_key(request, settings) == "user:user-123"


def test_resolve_rate_key_falls_back_to_client_ip_when_unauthenticated():
    from app.core.rate_limit import resolve_rate_key

    request = _FakeRequest({}, host="198.51.100.7")
    assert resolve_rate_key(request, _test_settings()) == "ip:198.51.100.7"


def test_forged_token_cannot_select_a_user_specific_key():
    # A token signed with a secret that is not the server's must never yield a
    # user key — the signature check fails and identity falls back to the IP.
    from app.auth.security import create_access_token
    from app.core.config import Settings
    from app.core.rate_limit import resolve_rate_key

    attacker = create_access_token("victim-id", Settings(app_env="test", auth_secret_key="x" * 40))
    request = _FakeRequest({"authorization": f"Bearer {attacker}"})

    assert resolve_rate_key(request, _test_settings()) == "ip:203.0.113.9"


def test_garbage_bearer_token_does_not_select_a_user_key():
    from app.core.rate_limit import resolve_rate_key

    request = _FakeRequest({"authorization": "Bearer not-a-real-token"})
    assert resolve_rate_key(request, _test_settings()) == "ip:203.0.113.9"


def test_forwarded_header_is_ignored_for_rate_key():
    # X-Forwarded-For is client-settable and must not influence the key; only
    # the direct socket peer address is used for the IP fallback.
    from app.core.rate_limit import resolve_rate_key

    request = _FakeRequest({"x-forwarded-for": "10.0.0.1"}, host="203.0.113.9")
    assert resolve_rate_key(request, _test_settings()) == "ip:203.0.113.9"


def test_two_authenticated_users_behind_one_ip_get_independent_budgets(limited_client):
    # limited_client is authenticated as the fixture user and shares one client
    # IP with a second user we register here.
    other = register_user(limited_client, "second-user@example.com")

    # The primary user exhausts the default budget (3/min)...
    for _ in range(3):
        assert limited_client.get("/repositories").status_code == 200
    assert limited_client.get("/repositories").status_code == 429

    # ...and the second user, same IP, still has a full budget.
    assert limited_client.get("/repositories", headers=other["headers"]).status_code == 200


def test_repeated_requests_from_one_user_consume_that_users_budget(limited_client):
    for _ in range(3):
        assert limited_client.get("/repositories").status_code == 200
    # The 4th request from the same user exceeds the 3/min default budget.
    assert limited_client.get("/repositories").status_code == 429


# --- memory store --------------------------------------------------------------


def test_memory_store_counts_and_resets_after_window():
    now = [1000.0]
    store = MemoryRateLimitStore(clock=lambda: now[0])

    counts = [_hit(store, "k", 60)[0] for _ in range(3)]
    assert counts == [1, 2, 3]

    _, retry_after = _hit(store, "k", 60)
    assert 1 <= retry_after <= 60

    now[0] += 61  # past the window: the counter starts over
    count, _ = _hit(store, "k", 60)
    assert count == 1


def test_memory_store_keys_are_independent():
    store = MemoryRateLimitStore(clock=lambda: 0.0)
    assert _hit(store, "a", 60)[0] == 1
    assert _hit(store, "b", 60)[0] == 1


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


def test_export_endpoint_is_charged_against_the_heavy_budget(limited_client):
    """Regression: classify() must key on the route FastAPI actually registers
    (POST /export), not a path that was never wired up. Both the import and the
    export below share the 2/min heavy budget, so if /export silently fell back
    to the (looser) default class this would never hit 429."""
    repository_id = _import_sample(limited_client)  # 1st heavy hit

    # "architecture" is used here (not "dependencies") because this repository
    # was only imported, never analysed, and Dependency Graph is now
    # sealed-snapshot-bound (#158) — it would 404 rather than exercise the
    # rate-limit budget this test actually targets.
    payload = {"repositoryId": repository_id, "target": "architecture", "format": "json"}
    assert limited_client.post("/export", json=payload).status_code == 200  # 2nd heavy hit

    blocked = limited_client.post("/export", json=payload)  # 3rd heavy hit
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["code"] == "rate_limited"
    assert body["details"]["retryAfterSeconds"] >= 1
    assert int(blocked.headers["Retry-After"]) >= 1


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
        async def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
            raise StoreUnavailableError("redis is down")

    from app.core.observability import runtime_metrics

    degraded_before = runtime_metrics.rate_limit_degraded_total
    limited_client.app.state.rate_limit_store = FailingStore()

    # Way past the budget, yet everything is served — and counted as degraded.
    for _ in range(5):
        assert limited_client.get("/repositories").status_code == 200
    assert runtime_metrics.rate_limit_degraded_total >= degraded_before + 5


def test_rate_limit_store_closed_on_app_shutdown(monkeypatch, tmp_path: Path) -> None:
    """The Redis store holds a connection pool; the app must close it on
    shutdown rather than leaking it, e.g. across a reload/redeploy."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'partha-test.db'}")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

    from app.core import config

    config.get_settings.cache_clear()

    from app.main import create_app

    closed = {"value": False}

    class StubStore:
        async def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
            return 1, 60

        async def aclose(self) -> None:
            closed["value"] = True

    monkeypatch.setattr("app.main.build_rate_limit_store", lambda settings: StubStore())

    with TestClient(create_app()) as test_client:
        assert closed["value"] is False
        test_client.get("/health")

    assert closed["value"] is True

    for key in ("DATABASE_URL", "STORAGE_PATH", "AUTO_CREATE_TABLES", "CORS_ORIGINS"):
        os.environ.pop(key, None)
    config.get_settings.cache_clear()


def test_rate_limit_store_closed_when_lifespan_exits_via_exception(monkeypatch, tmp_path: Path) -> None:
    """Cleanup after `yield` must run even when the lifespan's running state
    exits through an exception, not only on a clean shutdown — otherwise a crash
    while the app is running leaks the Redis connection pool instead of closing
    it, defeating the fix `test_rate_limit_store_closed_on_app_shutdown` proves
    for the clean-shutdown path."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'partha-test.db'}")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

    from app.core import config

    config.get_settings.cache_clear()

    from app.main import create_app, lifespan

    closed = {"value": False}

    class StubStore:
        async def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
            return 1, 60

        async def aclose(self) -> None:
            closed["value"] = True

    monkeypatch.setattr("app.main.build_rate_limit_store", lambda settings: StubStore())

    app = create_app()

    class Boom(Exception):
        pass

    async def scenario() -> None:
        with pytest.raises(Boom):
            async with lifespan(app):
                raise Boom("simulated failure while the app is running")

    asyncio.run(scenario())

    assert closed["value"] is True

    for key in ("DATABASE_URL", "STORAGE_PATH", "AUTO_CREATE_TABLES", "CORS_ORIGINS"):
        os.environ.pop(key, None)
    config.get_settings.cache_clear()


def test_metrics_endpoint_exposes_rate_limit_counters(limited_client):
    text = limited_client.get("/metrics").text
    assert "partha_rate_limited_requests_total" in text
    assert "partha_rate_limit_degraded_total" in text


def test_429_response_still_carries_cors_and_security_headers(limited_client):
    # RateLimitMiddleware is registered before SecurityHeadersMiddleware and
    # CORSMiddleware, so it sits innermost and its 429s must still pick up both
    # as they bubble back out — otherwise a browser client sees an opaque CORS
    # failure instead of a readable 429.
    origin = "http://testserver"
    for _ in range(3):
        assert limited_client.get("/repositories", headers={"Origin": origin}).status_code == 200

    blocked = limited_client.get("/repositories", headers={"Origin": origin})
    assert blocked.status_code == 429
    assert blocked.headers["access-control-allow-origin"] == origin
    assert blocked.headers["x-content-type-options"] == "nosniff"
    assert "retry-after" in blocked.headers
    assert "x-request-id" in blocked.headers


# --- real Redis backend (gated) -----------------------------------------------


@pytest.mark.skipif(not REDIS_URL, reason="set PARTHA_TEST_REDIS_URL to run the Redis backend test")
def test_redis_store_is_atomic_and_expires():
    """Exercise the actual RedisRateLimitStore against a real server: the atomic
    script counts up within a window, arms a bounded TTL, and isolates keys."""
    import redis.asyncio as redis_asyncio

    from app.core.rate_limit import RedisRateLimitStore

    async def scenario() -> None:
        client = redis_asyncio.from_url(REDIS_URL, decode_responses=False)
        store = RedisRateLimitStore(client)
        key_a = f"pytest:{uuid.uuid4()}"
        key_b = f"pytest:{uuid.uuid4()}"
        try:
            counts = [(await store.hit(key_a, 60))[0] for _ in range(3)]
            assert counts == [1, 2, 3]

            _, ttl = await store.hit(key_a, 60)
            assert 1 <= ttl <= 60  # armed once, bounded by the window

            # A different key is a separate budget.
            assert (await store.hit(key_b, 60))[0] == 1
        finally:
            await client.delete(f"partha:ratelimit:{key_a}", f"partha:ratelimit:{key_b}")
            await client.aclose()

    asyncio.run(scenario())


@pytest.mark.skipif(not REDIS_URL, reason="set PARTHA_TEST_REDIS_URL to run the Redis backend test")
def test_redis_store_atomic_under_concurrent_hits():
    """The separate INCR/EXPIRE calls this replaced had a race window; fire real
    concurrent hits at one key and prove the count is exact (no lost updates) —
    a sequential test can't distinguish an atomic script from a racy one."""
    import redis.asyncio as redis_asyncio

    from app.core.rate_limit import RedisRateLimitStore

    concurrency = 50

    async def scenario() -> None:
        client = redis_asyncio.from_url(REDIS_URL, decode_responses=False)
        store = RedisRateLimitStore(client)
        key = f"pytest:{uuid.uuid4()}"
        try:
            results = await asyncio.gather(*(store.hit(key, 60) for _ in range(concurrency)))
            counts = sorted(count for count, _ in results)
            # Every hit claimed a distinct, contiguous slot — no two racers
            # observed/wrote the same counter value, and none were lost.
            assert counts == list(range(1, concurrency + 1))
            ttls = {ttl for _, ttl in results}
            assert all(1 <= ttl <= 60 for ttl in ttls)
        finally:
            await client.delete(f"partha:ratelimit:{key}")
            await client.aclose()

    asyncio.run(scenario())
