"""Pinned HTTP sender shared by every AI provider implementation."""

from __future__ import annotations

from typing import Protocol

import anyio
import httpx

from app.core.ai_egress import DestinationPolicyError, ProviderEgressPolicy
from app.ai.types import AiProviderConfig
from app.core.exceptions import ExternalServiceError, TimeoutServiceError, ValidationServiceError


class ProviderHttpSender(Protocol):
    async def post(self, config: AiProviderConfig, url: str, **kwargs: object) -> httpx.Response:
        raise NotImplementedError


class RedirectDeniedError(Exception):
    """Signals a redirect without ever evaluating its Location header."""


class SecureProviderHttpSender:
    """Send one provider request through the central policy and a pinned IP.

    The policy resolves and validates the original hostname immediately before
    this method creates a request.  The request URL uses the resulting literal
    IP, while ``Host`` and HTTPS SNI retain the normalized original hostname.
    ``trust_env=False`` prevents environment proxy settings from sending the
    request around the policy.
    """

    def __init__(self, policy: ProviderEgressPolicy, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.policy = policy
        self.transport = transport

    async def post(self, config: AiProviderConfig, url: str, **kwargs: object) -> httpx.Response:
        # Policy preparation performs DNS resolution. Keep that blocking call
        # off the event loop used by the async AI routes.
        pinned = await anyio.to_thread.run_sync(self.policy.prepare_request, config, url)
        request_headers = httpx.Headers(kwargs.pop("headers", None))
        # The original authority, never the pinned IP, is what the provider and
        # virtual host expect.  Overwrite rather than trust a caller-provided
        # Host header so there is a single validated destination identity.
        request_headers["Host"] = pinned.destination.host_header
        # Make the production retry policy explicit. A connection retry must
        # never trigger another hostname resolution inside the HTTP stack; the
        # application instead fails and revalidates DNS on the next request.
        transport = self.transport or httpx.AsyncHTTPTransport(verify=True, retries=0)

        async with httpx.AsyncClient(
            timeout=60,
            verify=True,
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        ) as client:
            request = client.build_request("POST", pinned.connection_url, headers=request_headers, **kwargs)
            # httpcore's documented request extension preserves TLS SNI (and
            # therefore hostname verification) when connecting to a literal IP.
            request.extensions["sni_hostname"] = pinned.destination.host
            response = await client.send(request)

        if 300 <= response.status_code < 400:
            raise RedirectDeniedError()
        return response


def _default_sender() -> SecureProviderHttpSender:
    # Keep the import lazy to avoid a config -> provider import cycle and to
    # make the production resolver easy to replace in direct unit tests.
    from app.core.config import get_settings

    return SecureProviderHttpSender(ProviderEgressPolicy.from_settings(get_settings()))


def require_api_key(config: AiProviderConfig) -> None:
    if not config.api_key:
        raise ValidationServiceError("API key is required for the selected AI provider.")


def _plain_language_status_error(config: AiProviderConfig, exc: httpx.HTTPStatusError) -> Exception:
    """Translate a provider's HTTP status into one of #291's named plain-
    language failure modes, using only the status code -- never the response
    body, whose shape differs per provider and could itself carry sensitive
    detail worth not repeating verbatim to the client."""

    status = exc.response.status_code
    if status in (401, 403):
        return ValidationServiceError(
            "AI provider rejected the API key. Confirm the key is correct and still active, then save it again.",
            {"provider": config.provider},
        )
    if status == 429:
        return ExternalServiceError(
            "AI provider rate limit reached. Wait a moment and try again.",
            {"provider": config.provider},
        )
    if status in (400, 404, 422):
        return ValidationServiceError(
            "AI provider rejected the request, most likely because of an unsupported model ID. "
            "Confirm the model ID and try again.",
            {"provider": config.provider},
        )
    return ExternalServiceError("AI provider request failed.", {"provider": config.provider})


async def post(
    config: AiProviderConfig,
    url: str,
    *,
    sender: ProviderHttpSender | None = None,
    **kwargs: object,
) -> httpx.Response:
    """Apply normalized provider errors around the central outbound sender."""

    active_sender = sender or _default_sender()
    try:
        response = await active_sender.post(config, url, **kwargs)
        response.raise_for_status()
        return response
    except DestinationPolicyError as exc:
        raise ValidationServiceError("AI provider destination is not permitted.") from exc
    except RedirectDeniedError as exc:
        raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
    except httpx.HTTPStatusError as exc:
        raise _plain_language_status_error(config, exc) from exc
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        # httpx.ConnectTimeout does NOT inherit from httpx.ConnectError in
        # this version (both are separate httpx.TransportError subclasses),
        # so it needs its own explicit clause here, ahead of the broader
        # httpx.TimeoutException below -- a timeout during the connect phase
        # itself (as opposed to a slow response after connecting fine) reads
        # the same as "unreachable" here. The most common cause in practice
        # is a local/self-hosted provider (Ollama) that isn't running, or a
        # base URL that's wrong -- both surface identically at this layer,
        # so the message covers both rather than guessing which one it was.
        raise ExternalServiceError(
            "Could not reach the AI provider. If it's self-hosted (e.g. Ollama), confirm it's running and "
            "the base URL is correct.",
            {"provider": config.provider},
        ) from exc
    except httpx.TimeoutException as exc:
        raise TimeoutServiceError(
            "AI provider did not respond in time. Try again in a moment.",
            {"provider": config.provider},
        ) from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
