import base64
from collections.abc import Awaitable, Callable
import hashlib
from html.parser import HTMLParser

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


class _InlineScriptCollector(HTMLParser):
    """Collect the exact text of every inline <script> (one without src).

    A real parser rather than a regex: it matches the tag in any case and with
    any attributes, which is what the browser does when it checks the hash.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[str] = []
        self._current: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and not any(name == "src" for name, _ in attrs):
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._current is not None:
            self.scripts.append("".join(self._current))
            self._current = None


def _inline_scripts(index_html: str) -> list[str]:
    collector = _InlineScriptCollector()
    collector.feed(index_html)
    collector.close()
    return collector.scripts


def frontend_content_security_policy(index_html: str) -> str:
    """CSP for the SPA shell when this service also serves the built frontend (#339).

    The API's deny-all policy above blocks every script and stylesheet the page
    needs, so the shell gets its own. Inline scripts in index.html are allowed by
    hash, computed from the built file itself so editing that script can never
    silently break the page. Third-party origins are exactly the ones the
    frontend loads today: Google Fonts, and the Monaco editor from jsDelivr,
    which runs its language workers from blob: URLs. Inline styles are allowed
    because the graph and editor libraries inject their own.
    """

    script_sources = [
        "'self'",
        *(
            "'sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode() + "'"
            for body in _inline_scripts(index_html)
        ),
        "https://cdn.jsdelivr.net",
    ]
    directives = [
        "default-src 'self'",
        "script-src " + " ".join(script_sources),
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net",
        "img-src 'self' data: blob:",
        "worker-src 'self' blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
    ]
    return "; ".join(directives)


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
