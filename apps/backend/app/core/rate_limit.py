import logging
import math
import time
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.security import decode_access_token
from app.core.config import Settings
from app.core.exceptions import ErrorResponse, UnauthorizedError
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
        path in {"/repositories/upload", "/repositories/github", "/documentation/generate", "/export"}
        or (path.startswith("/analysis/") and path.endswith("/start"))
    ):
        return "heavy"
    return "default"


def _authenticated_user_id(request: Request, settings: Settings) -> str | None:
    """The user id from a valid Bearer access token, or None.

    The token's signature is verified with the server's own signing key
    (``decode_access_token``), so identity is never taken from an unverified
    JWT: a forged, expired, or malformed token — or one signed by anyone but
    us — yields None and falls back to the client IP. Only the ``Authorization``
    header is consulted; a raw bearer string, email, or forwarded header can
    never select a user-specific budget.
    """
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        return decode_access_token(token.strip(), settings)
    except UnauthorizedError:
        return None


def resolve_rate_key(request: Request, settings: Settings) -> str:
    """Identity a budget is charged against.

    Authenticated requests are keyed on the validated user id, so two signed-in
    users behind one NAT'd address get independent budgets and one user cannot
    exhaust another's by sharing an IP. Unauthenticated (and forged-token)
    requests fall back to the direct socket peer address.

    Trusted-proxy caveat: the IP fallback reads ``request.client.host``, the
    direct TCP peer. Behind a reverse proxy that is the proxy's address, so
    every unauthenticated client would share one budget. Honouring
    ``X-Forwarded-For`` safely needs a trusted-proxy allowlist (which hop to
    believe) — deliberately NOT implemented here, because trusting a
    client-settable header without one turns the limiter into a trivially
    spoofable no-op. Enable forwarded-header parsing only once the deployment's
    proxy topology is known.
    """
    user_id = _authenticated_user_id(request, settings)
    if user_id is not None:
        return f"user:{user_id}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


class StoreUnavailableError(Exception):
    """The backing store cannot be reached; the middleware fails open."""


class RateLimitStore(Protocol):
    """A fixed-window counter keyed by an arbitrary string."""

    async def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
        """Record one hit; return (count in current window, seconds to reset)."""


class MemoryRateLimitStore:
    """Fixed-window counters in process memory.

    Deterministic (the clock is injectable) and per-process — the right
    behaviour for tests and single-instance development, and the fallback when
    Redis is not configured. ``hit`` is async only to satisfy the store
    interface; it does no I/O and never blocks the event loop.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    async def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
        now = self._clock()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start >= window_seconds:
                window_start, count = now, 0
            count += 1
            self._windows[key] = (window_start, count)
        retry_after = max(1, math.ceil(window_seconds - (now - window_start)))
        return count, retry_after


# Runs atomically on the server in a single round trip: increment the counter,
# arm the TTL on the first hit of a window (and re-arm if a key somehow lost its
# expiry), and return count + remaining TTL together. This closes the race the
# separate INCR/EXPIRE/TTL calls had, and keeps the hot path to one network hop.
_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
else
  local ttl = redis.call('TTL', KEYS[1])
  if ttl < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
  end
end
return {count, redis.call('TTL', KEYS[1])}
"""


class RedisRateLimitStore:
    """Fixed-window counters shared across processes via an atomic Redis script.

    Uses ``redis.asyncio`` so the network round trip is awaited rather than
    blocking the event loop.
    """

    def __init__(self, client) -> None:
        self._client = client
        self._script = client.register_script(_WINDOW_SCRIPT)

    async def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
        redis_key = f"partha:ratelimit:{key}"
        try:
            count, ttl = await self._script(keys=[redis_key], args=[window_seconds])
        except Exception as exc:
            raise StoreUnavailableError(str(exc)) from exc
        return int(count), max(1, int(ttl))

    async def aclose(self) -> None:
        await self._client.aclose()


def build_rate_limit_store(settings: Settings) -> RateLimitStore:
    if settings.rate_limit_backend == "redis":
        import redis.asyncio as redis_asyncio

        client = redis_asyncio.from_url(settings.redis_url, decode_responses=False)
        return RedisRateLimitStore(client)
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
        key = f"{budget_class}:{resolve_rate_key(request, settings)}"

        store: RateLimitStore = request.app.state.rate_limit_store
        try:
            count, retry_after = await store.hit(key, WINDOW_SECONDS)
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
