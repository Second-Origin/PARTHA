"""Shared truth rules for observed outbound HTTP call sites (#209).

The Python and TypeScript extractors recognize different client libraries, but a
service interaction means the same thing in both: *this source line proves a
request to this destination*. The rules for turning a literal URL into a
deterministic identity therefore live here once, so the two extractors cannot
drift into disagreeing about what counts as a destination.

Two decisions are deliberate and load-bearing:

**Identity is the origin, not the URL.** ``scheme://host[:port]`` is what a
service *is*; ``/v1/users`` is what one call site asked it for. Folding the path
into the node key would produce one "service" per endpoint and make the graph
useless for impact questions, so the path travels on the call's own observation
instead.

**The query string is dropped.** A literal URL in source can carry an API key or
token in its query (``?api_key=...``). Diagnostics and stored facts must not
embed secrets (RFC §13), and the query is not part of the destination's
identity, so it is discarded rather than recorded. Userinfo credentials
(``https://user:pass@host``) are stripped from the origin for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

#: Client attribute names that name their own HTTP method (``requests.get``,
#: ``session.post``, ``axios.delete``). ``request``-style calls take the method
#: as an argument and are handled separately by each extractor.
HTTP_METHOD_ATTRIBUTES = frozenset({"delete", "get", "head", "options", "patch", "post", "put"})

#: Only these schemes describe an HTTP service interaction. Anything else
#: (``file:``, ``ws:``, ``data:``) is not one and is never recorded as one.
_SUPPORTED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": "80", "https": "443"}


@dataclass(frozen=True)
class HttpDestination:
    """A syntax-proven destination: an absolute origin plus a literal method."""

    method: str
    origin: str
    path: str

    @property
    def referent_text(self) -> str:
        """The observation referent: ``<METHOD>|<origin>|<path>``.

        A single delimited field keeps the observation identity (RFC §6.4) exact
        while still letting the resolver recover the origin without re-parsing
        source, mirroring how ``import_binding`` stores its three parts. ``|``
        cannot appear in a normalized origin or in an HTTP method token.
        """

        return f"{self.method}|{self.origin}|{self.path}"


def normalize_method(raw: str) -> str | None:
    """Return the canonical uppercase method token, or ``None`` if implausible.

    Methods are matched as whole ASCII tokens so a computed value that happens
    to be a string (``"GET " + suffix`` folded by a compiler, a header blob)
    cannot be mistaken for a proven method.
    """

    token = raw.strip().upper()
    if not token or not token.isascii() or not token.isalpha():
        return None
    return token


def _split_origin(url: str) -> tuple[str, str] | None:
    """Parse ``url`` and return ``(origin, path)``, or ``None``.

    Shared by both entry points below: neither a fully literal URL nor a
    literal f-string/template-literal prefix trusts a scheme, host, or origin
    that don't come out of this one check.
    """

    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in _SUPPORTED_SCHEMES or not parts.hostname:
        return None
    host = parts.hostname.lower().rstrip(".")
    if not host:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    origin = f"{scheme}://{host}"
    if port is not None and str(port) != _DEFAULT_PORTS[scheme]:
        origin = f"{origin}:{port}"
    return origin, parts.path


def describe_destination(method: str, url: str) -> HttpDestination | None:
    """Build a destination from a literal method and URL, or ``None``.

    ``None`` means the URL is not an absolute ``http``/``https`` address — a
    relative path, a scheme-relative ``//host`` reference, a non-HTTP scheme, or
    a host-less string. None of those identify a service on their own, and the
    caller turns each into an explicit diagnostic rather than a guessed edge.
    """

    normalized_method = normalize_method(method)
    if normalized_method is None:
        return None
    split = _split_origin(url)
    if split is None:
        return None
    origin, path = split
    return HttpDestination(method=normalized_method, origin=origin, path=path or "/")


def describe_destination_from_literal_prefix(method: str, literal_prefix: str) -> HttpDestination | None:
    """Build a destination from an f-string/template-literal's leading literal
    text -- everything from the start of the string up to its first
    interpolation -- or ``None``.

    Origin identity is only ``scheme://host[:port]``, so a call like
    ``f"https://api.example.com/users/{user_id}"`` proves its destination
    origin from ``literal_prefix`` alone even though the full URL isn't a
    compile-time constant: nothing after the authority can change what
    service this is.

    That's only true once the authority is *closed off* within the literal
    text, though -- ``literal_prefix`` must already contain the ``/`` that
    starts the path (or the caller wouldn't have anything left to
    interpolate into the URL at all). Without it, the interpolation could
    still be extending the host itself (``f"https://{tenant}.example.com"``,
    or the more dangerous ``f"https://api.example.com{suffix}"`` where a
    ``suffix`` that doesn't start with ``/`` silently becomes part of the
    hostname), and there is no origin here to trust.
    """

    normalized_method = normalize_method(method)
    if normalized_method is None:
        return None
    split = _split_origin(literal_prefix)
    if split is None:
        return None
    origin, path = split
    if not path:
        return None
    return HttpDestination(method=normalized_method, origin=origin, path=path)


def parse_referent(referent: str) -> HttpDestination | None:
    """Recover a destination from a stored ``http_call`` referent.

    Used by the resolver, which reads persisted observations and never re-reads
    source. A referent that does not have exactly the three expected parts is
    not silently repaired.
    """

    parts = referent.split("|")
    if len(parts) != 3 or not all(parts):
        return None
    return HttpDestination(method=parts[0], origin=parts[1], path=parts[2])
