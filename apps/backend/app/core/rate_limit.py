import logging
import math
import time
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.exceptions import ErrorResponse
from app.core.observability import get_request_id, runtime_metrics

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60

# Never rate-limited: operational probes must stay available under abuse, the
# docs are static, and OPTIONS is CORS preflight — a 429 there would surface as
# an opaque CORS failure in the browser instead of a readable error.
EXEMPT_PATHS = {"/health", "/ready", "/metrics"}
EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")


def classify(method: str, path: str) -> str | None:
    """Map a request to a budget class, or None when exempt.

    The auth entries are inert until the /auth router merges; they are listed
    now so the brute-force budget applies the moment it does.
    """
    if method == "OPTIONS" or path in EXEMPT_PATHS or path.startswith(EXEMPT_PREFIXES):
        return None
    if method == "POST" and path in {"/auth/login", "/auth/register"}:
        return "auth"
    if path == "/ai" or path.startswith("/ai/"):
        return "ai"
    if method == "POST" and (
        path in {"/repositories/upload", "/repositories/github", "/documentation/generate", "/reports/export"}
        or (path.startswith("/analysis/") and path.endswith("/start"))
    ):
        return "heavy"
    return "default"


def resolve_rate_key(request: Request) -> str:
    """Identity a budget is charged against: the client IP for now.

    E1.3 upgrades this to the authenticated user id when a valid Bearer token
    is present, so signed-in users get per-user budgets instead of sharing a
    NAT'd address.
    """
    client = request.client
    return client.host if client else "unknown"


class StoreUnavailableError(Exception):
    """The backing store cannot be reached; the middleware fails open."""


class RateLimitStore(Protocol):
    def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
        """Record one hit; return (count in current window, seconds to reset)."""
        ...


class MemoryRateLimitStore:
    """Fixed-window counters in process memory.

    Deterministic (the clock is injectable) and per-process — the right
    behaviour for tests and single-instance development, and the fallback when
    Redis is not configured.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
        now = self._clock()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start >= window_seconds:
                window_start, count = now, 0
            count += 1
            self._windows[key] = (window_start, count)
        retry_after = max(1, math.ceil(window_seconds - (now - window_start)))
        return count, retry_after


class RedisRateLimitStore:
    """Fixed-window counters shared across processes via Redis INCR+EXPIRE."""

    def __init__(self, client) -> None:
        self._client = client

    def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
        redis_key = f"partha:ratelimit:{key}"
        try:
            count = self._client.incr(redis_key)
            if count == 1:
                self._client.expire(redis_key, window_seconds)
            ttl = self._client.ttl(redis_key)
            if ttl is None or ttl < 0:
                # The key lost its expiry (e.g. crash between INCR and EXPIRE);
                # re-arm it rather than rate-limiting forever.
                self._client.expire(redis_key, window_seconds)
                ttl = window_seconds
        except Exception as exc:
            raise StoreUnavailableError(str(exc)) from exc
        return int(count), max(1, int(ttl))


def build_rate_limit_store(settings: Settings) -> RateLimitStore:
    if settings.rate_limit_backend == "redis":
        from app.core.redis import create_redis_client

        return RedisRateLimitStore(create_redis_client())
    return MemoryRateLimitStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-identity fixed-window budgets, stricter on expensive routes.

    The store is read from ``app.state.rate_limit_store`` on every request so
    tests (and future operational tooling) can swap it without rebuilding the
    app. Store failures fail OPEN: availability wins over strictness for a
    self-hosted tool, but every degraded request is logged and counted so the
    condition is impossible to miss.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings: Settings = request.app.state.rate_limit_settings
        if not settings.rate_limit_enabled:
            return await call_next(request)

        budget_class = classify(request.method, request.url.path)
        if budget_class is None:
            return await call_next(request)

        budgets = {
            "auth": settings.rate_limit_auth_per_minute,
            "ai": settings.rate_limit_ai_per_minute,
            "heavy": settings.rate_limit_heavy_per_minute,
            "default": settings.rate_limit_default_per_minute,
        }
        limit = budgets[budget_class]
        key = f"{budget_class}:{resolve_rate_key(request)}"

        store: RateLimitStore = request.app.state.rate_limit_store
        try:
            count, retry_after = store.hit(key, WINDOW_SECONDS)
        except StoreUnavailableError:
            runtime_metrics.record_rate_limit_degraded()
            logger.warning(
                "Rate-limit store unavailable; allowing request unchecked",
                extra={"path": request.url.path, "budget_class": budget_class},
            )
            return await call_next(request)

        if count > limit:
            runtime_metrics.record_rate_limited()
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content=ErrorResponse(
                    code="rate_limited",
                    message="Too many requests. Try again shortly.",
                    details={"retryAfterSeconds": retry_after},
                    request_id=get_request_id(),
                ).model_dump(),
            )
        return await call_next(request)
