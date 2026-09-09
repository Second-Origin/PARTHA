"""Central destination policy for outbound AI-provider traffic.

This module deliberately has no dependency on the HTTP client or persistence
layers.  It validates a provider configuration before it is saved and produces
an IP-pinned destination immediately before a request is sent.  Keeping that
logic here makes the policy straightforward to unit test with a fake resolver.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import ipaddress
import re
import socket
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit


_ALLOWED_SCHEMES = {"http", "https"}
_DEFAULT_PORTS = {"http": 80, "https": 443}
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_NUMERIC_DOTTED_HOST = re.compile(r"[0-9.]+$")


class DestinationPolicyError(ValueError):
    """A deliberately non-specific policy denial safe to return to callers."""

    def __init__(self) -> None:
        super().__init__("AI provider destination is not permitted.")


class DestinationPolicyConfigurationError(ValueError):
    """Raised for an invalid administrator-owned policy setting."""


class ProviderConfigLike(Protocol):
    provider: str
    base_url: str | None


Resolver = Callable[[str, int], Sequence[str]]


@dataclass(frozen=True)
class NormalizedDestination:
    """A canonical URL suitable for exact policy comparison.

    ``host`` never includes IPv6 brackets; ``port`` is always explicit in the
    data model even when it is omitted from the canonical URL.
    """

    scheme: str
    host: str
    port: int
    path: str
    query: str = ""

    @property
    def is_ip_literal(self) -> bool:
        try:
            ipaddress.ip_address(self.host)
        except ValueError:
            return False
        return True

    @property
    def authority(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        if self.port != _DEFAULT_PORTS[self.scheme]:
            return f"{host}:{self.port}"
        return host

    @property
    def base_url(self) -> str:
        return urlunsplit((self.scheme, self.authority, self.path, "", ""))

    @property
    def request_url(self) -> str:
        return urlunsplit((self.scheme, self.authority, self.path, self.query, ""))

    @property
    def host_header(self) -> str:
        return self.authority

    def pinned_request_url(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
        host = str(address)
        authority = f"[{host}]" if address.version == 6 else host
        if self.port != _DEFAULT_PORTS[self.scheme]:
            authority = f"{authority}:{self.port}"
        return urlunsplit((self.scheme, authority, self.path, self.query, ""))


@dataclass(frozen=True)
class PinnedDestination:
    """A destination whose connection address was validated immediately before use."""

    destination: NormalizedDestination
    address: ipaddress.IPv4Address | ipaddress.IPv6Address

    @property
    def connection_url(self) -> str:
        return self.destination.pinned_request_url(self.address)


@dataclass(frozen=True)
class _FixedProviderDestination:
    scheme: str
    host: str
    base_path: str


# These origins are intentionally code-owned.  A tenant can select a provider
# and model, but can never replace a cloud provider's destination.
FIXED_PROVIDER_DESTINATIONS: dict[str, _FixedProviderDestination] = {
    "openai": _FixedProviderDestination("https", "api.openai.com", "/v1"),
    "anthropic": _FixedProviderDestination("https", "api.anthropic.com", "/v1"),
    "gemini": _FixedProviderDestination("https", "generativelanguage.googleapis.com", "/v1beta"),
    "openrouter": _FixedProviderDestination("https", "openrouter.ai", "/api/v1"),
}


def _deny() -> DestinationPolicyError:
    return DestinationPolicyError()


def _configuration_error(message: str) -> DestinationPolicyConfigurationError:
    return DestinationPolicyConfigurationError(message)


def _canonical_host(raw_host: str) -> str:
    # A single fully-qualified-domain trailing dot has one unambiguous meaning;
    # multiple dots are an unsafe alternate spelling and are rejected.
    if raw_host.endswith(".."):
        raise _deny()
    host = raw_host[:-1] if raw_host.endswith(".") else raw_host
    if not host:
        raise _deny()

    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass

    # Decimal, octal, hexadecimal, and shortened IPv4 representations have
    # inconsistent parser behaviour across libraries.  Treat a numeric-looking
    # non-canonical host as ambiguous instead of trying to reinterpret it.
    if _NUMERIC_DOTTED_HOST.fullmatch(host) or host.lower().startswith("0x"):
        raise _deny()

    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise _deny() from exc

    if len(host) > 253 or not host or host.startswith(".") or host.endswith("."):
        raise _deny()
    labels = host.split(".")
    if any(not _HOST_LABEL.fullmatch(label) for label in labels):
        raise _deny()
    return host


def _normalise_path(path: str) -> str:
    if not path:
        return "/"
    if not path.startswith("/") or "\\" in path or "%" in path:
        raise _deny()
    segments = path.split("/")
    if any(segment in {".", ".."} for segment in segments):
        raise _deny()
    # Empty segments in the middle are a second spelling for a different or
    # implementation-defined route.  A trailing slash is harmless and is
    # normalized so administrator entries compare consistently.
    if any(not segment for segment in segments[1:-1]):
        raise _deny()
    return path.rstrip("/") or "/"


def _normalise_url(value: str | None, *, allow_query: bool) -> NormalizedDestination:
    if not isinstance(value, str) or not value or value != value.strip():
        raise _deny()
    if any(ord(character) <= 0x20 for character in value) or "\\" in value or "%" in value:
        raise _deny()
    if "#" in value or (not allow_query and "?" in value):
        raise _deny()

    try:
        parsed = urlsplit(value, allow_fragments=True)
    except ValueError as exc:
        raise _deny() from exc

    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES or not parsed.netloc or parsed.fragment:
        raise _deny()
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise _deny()
    if not allow_query and parsed.query:
        raise _deny()

    try:
        raw_host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise _deny() from exc
    if raw_host is None or parsed.netloc.rsplit("@", maxsplit=1)[-1].endswith(":"):
        raise _deny()

    host = _canonical_host(raw_host)
    port = port if port is not None else _DEFAULT_PORTS[scheme]
    if not 1 <= port <= 65535:
        raise _deny()

    return NormalizedDestination(
        scheme=scheme,
        host=host,
        port=port,
        path=_normalise_path(parsed.path),
        query=parsed.query if allow_query else "",
    )


def normalize_base_url(value: str | None) -> NormalizedDestination:
    """Normalize an administrator-configured provider base URL.

    Base URLs cannot carry a query or fragment, because those would make exact
    destination comparison ambiguous.
    """

    return _normalise_url(value, allow_query=False)


def normalize_request_url(value: str | None) -> NormalizedDestination:
    """Normalize a provider request URL without exposing the original value."""

    return _normalise_url(value, allow_query=True)


def resolve_hostname(host: str, port: int) -> Sequence[str]:
    """Return DNS answers without choosing a connection address yet."""

    records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return tuple(record[4][0] for record in records)


def _is_permitted_address_class(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    allow_internal: bool,
) -> bool:
    """Return whether an address class is safe for a provider connection.

    ``is_global`` alone is not a public-unicast test: Python correctly reports
    globally scoped multicast as global.  Unspecified, multicast, link-local,
    reserved, scoped IPv6, and non-global shared address space are never valid
    provider connection targets.  Explicit self-hosted policy may additionally
    admit private or loopback unicast addresses, but only after CIDR matching.

    PARTHA supports Python 3.12 and 3.13. The explicit address-class regression
    cases pin the intended policy across those stdlib ``ipaddress`` versions;
    review them whenever the supported Python range changes.
    """

    if isinstance(address, ipaddress.IPv6Address):
        if address.scope_id is not None:
            return False
        if address.ipv4_mapped is not None:
            return _is_permitted_address_class(address.ipv4_mapped, allow_internal=allow_internal)

    if address.is_unspecified or address.is_multicast or address.is_link_local:
        return False
    if allow_internal and address.is_loopback:
        return True
    if address.is_reserved:
        return False
    if allow_internal:
        return address.is_global or address.is_private
    return address.is_global


class ProviderEgressPolicy:
    """Validate AI-provider destinations at save time and request time."""

    def __init__(
        self,
        *,
        mode: str,
        allowed_base_urls: Sequence[str] = (),
        allowed_cidrs: Sequence[str] = (),
        resolver: Resolver = resolve_hostname,
    ) -> None:
        if not isinstance(mode, str):
            raise _configuration_error("AI_EGRESS_MODE must be either 'hosted' or 'self_hosted'.")
        normalized_mode = mode.lower()
        if normalized_mode not in {"hosted", "self_hosted"}:
            raise _configuration_error("AI_EGRESS_MODE must be either 'hosted' or 'self_hosted'.")
        self.mode = normalized_mode
        self.resolver = resolver
        # Settings normalizes deployment values at startup; repeat the work
        # here so direct construction in tests and other callers is equally
        # strict and cannot bypass canonical comparison.
        try:
            self.allowed_base_urls = frozenset(normalize_base_url(value).base_url for value in allowed_base_urls)
        except (DestinationPolicyError, TypeError) as exc:
            raise _configuration_error("AI_EGRESS_ALLOWED_BASE_URLS contains an invalid URL.") from exc
        try:
            self.allowed_cidrs = tuple(ipaddress.ip_network(value, strict=True) for value in allowed_cidrs)
        except (TypeError, ValueError) as exc:
            raise _configuration_error("AI_EGRESS_ALLOWED_CIDRS contains an invalid CIDR.") from exc

    @classmethod
    def from_settings(cls, settings: object, *, resolver: Resolver = resolve_hostname) -> "ProviderEgressPolicy":
        return cls(
            mode=getattr(settings, "ai_egress_mode"),
            allowed_base_urls=getattr(settings, "ai_egress_allowed_base_urls"),
            allowed_cidrs=getattr(settings, "ai_egress_allowed_cidrs"),
            resolver=resolver,
        )

    def validate_config(self, config: ProviderConfigLike) -> None:
        """Validate a user-supplied configuration before persistence.

        Fixed cloud providers have no configurable endpoint.  For Ollama, both
        the exact normalized base URL and its current DNS result must satisfy
        the deployment policy before a record is created or changed.
        """

        if config.provider in FIXED_PROVIDER_DESTINATIONS:
            if config.base_url is not None:
                raise _deny()
            return
        base = self._configurable_base(config)
        self._validated_addresses(base, configurable=True)

    def prepare_request(self, config: ProviderConfigLike, request_url: str) -> PinnedDestination:
        """Re-check policy and return a DNS-pinned connection destination."""

        destination = normalize_request_url(request_url)
        if config.provider in FIXED_PROVIDER_DESTINATIONS:
            self._validate_fixed_request(config, destination)
            addresses = self._validated_addresses(destination, configurable=False)
        else:
            base = self._configurable_base(config)
            self._require_under_base(destination, base)
            addresses = self._validated_addresses(destination, configurable=True)
        return PinnedDestination(destination=destination, address=addresses[0])

    def _configurable_base(self, config: ProviderConfigLike) -> NormalizedDestination:
        if config.provider != "ollama":
            raise _deny()
        base = normalize_base_url(config.base_url)
        if base.base_url not in self.allowed_base_urls:
            raise _deny()
        return base

    def _validate_fixed_request(self, config: ProviderConfigLike, destination: NormalizedDestination) -> None:
        if config.base_url is not None:
            raise _deny()
        expected = FIXED_PROVIDER_DESTINATIONS[config.provider]
        if destination.scheme != expected.scheme or destination.host != expected.host:
            raise _deny()
        if destination.port != _DEFAULT_PORTS[expected.scheme]:
            raise _deny()
        if destination.path != expected.base_path and not destination.path.startswith(f"{expected.base_path}/"):
            raise _deny()

    def _require_under_base(self, destination: NormalizedDestination, base: NormalizedDestination) -> None:
        if (
            destination.scheme != base.scheme
            or destination.host != base.host
            or destination.port != base.port
            or (base.path != "/" and destination.path != base.path and not destination.path.startswith(f"{base.path}/"))
        ):
            raise _deny()

    def _validated_addresses(
        self,
        destination: NormalizedDestination,
        *,
        configurable: bool,
    ) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
        if destination.is_ip_literal:
            answers: Sequence[str] = (destination.host,)
        else:
            try:
                answers = self.resolver(destination.host, destination.port)
            except Exception as exc:
                raise _deny() from exc

        if isinstance(answers, (str, bytes)) or not answers:
            raise _deny()

        resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        seen: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        for answer in answers:
            try:
                address = ipaddress.ip_address(answer)
            except (TypeError, ValueError) as exc:
                raise _deny() from exc
            if address not in seen:
                seen.add(address)
                resolved.append(address)
        if not resolved:
            raise _deny()

        allow_internal = configurable and self.mode == "self_hosted"
        if any(not _is_permitted_address_class(address, allow_internal=allow_internal) for address in resolved):
            raise _deny()

        if allow_internal:
            if not self.allowed_cidrs or any(
                not any(address in network for network in self.allowed_cidrs) for address in resolved
            ):
                raise _deny()
        return tuple(resolved)
