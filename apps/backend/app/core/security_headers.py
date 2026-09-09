from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Applied to every response. HSTS is honoured by browsers only over HTTPS, so
# sending it over plain HTTP (local dev) is silently ignored and safe to leave on.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}

# PARTHA's API returns JSON and never needs to load, frame, or embed anything, so
# the policy is deny-all. The one exception is the interactive API docs, which
# render HTML that pulls Swagger/ReDoc assets; CSP is skipped for those paths only
# (the other headers still apply).
CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
CSP_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response.

    Uses ``setdefault`` so a handler that deliberately sets one of these headers
    (e.g. a route needing a looser CSP) is never overridden.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if not request.url.path.startswith(CSP_EXEMPT_PREFIXES):
            response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response
