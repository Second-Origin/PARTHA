"""Model discovery: ask the provider what a key can use (#291).

A hardcoded default is a fact with a shelf life. `gemini-1.5-flash` stopped
being available to newly created Google AI Studio projects, so a first-time
user met "AI provider rejected the request" with nothing on screen telling
them what to type instead. These tests cover the route out of that: the list
comes from the provider, over the same pinned egress a completion uses.
"""

import asyncio
from typing import Any

import httpx
import pytest

from app.ai.providers.models import list_models, preferred_model
from app.ai.types import AiProviderConfig
from app.core.exceptions import ExternalServiceError, ValidationServiceError


class RecordingSender:
    """Captures the outbound request and replays a canned provider body."""

    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.calls: list[dict[str, Any]] = []

    async def post(self, config: AiProviderConfig, url: str, **kwargs: object) -> httpx.Response:
        raise AssertionError("model discovery must not POST")

    async def send(self, method: str, config: AiProviderConfig, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        return httpx.Response(self.status, json=self.payload, request=httpx.Request(method, "https://provider.example"))


@pytest.mark.parametrize(
    ("provider", "base_url", "payload", "expected", "host"),
    [
        (
            "openai",
            None,
            {"data": [{"id": "gpt-4.1-mini"}, {"id": "gpt-4.1"}]},
            ["gpt-4.1", "gpt-4.1-mini"],
            "api.openai.com",
        ),
        (
            "anthropic",
            None,
            {"data": [{"id": "claude-haiku-4-5"}, {"id": "claude-sonnet-4-5"}]},
            ["claude-haiku-4-5", "claude-sonnet-4-5"],
            "api.anthropic.com",
        ),
        (
            "openrouter",
            None,
            {"data": [{"id": "openai/gpt-4.1-mini"}]},
            ["openai/gpt-4.1-mini"],
            "openrouter.ai",
        ),
        (
            "ollama",
            "http://localhost:11434",
            {"models": [{"name": "llama3.2"}, {"name": "qwen2.5-coder"}]},
            ["llama3.2", "qwen2.5-coder"],
            "localhost",
        ),
    ],
)
def test_each_provider_reports_its_own_models(provider, base_url, payload, expected, host):
    sender = RecordingSender(payload)
    config = AiProviderConfig(provider=provider, api_key="key", base_url=base_url)

    models = asyncio.run(list_models(config, sender=sender))

    assert models == expected
    # A GET, against that provider's own host -- the same destination the
    # egress policy already permits for a completion, never a new one.
    assert sender.calls[0]["method"] == "GET"
    assert host in sender.calls[0]["url"]


def test_gemini_drops_models_that_cannot_answer_a_prompt():
    """Gemini lists everything the key can see, including embedding-only
    models. Offering one of those as a chat model would produce a failure the
    user could not diagnose, so they never reach the list."""

    sender = RecordingSender(
        {
            "models": [
                {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
    )

    models = asyncio.run(list_models(AiProviderConfig(provider="gemini", api_key="key"), sender=sender))

    assert models == ["gemini-2.0-flash", "gemini-2.5-pro"]
    assert "text-embedding-004" not in models


def test_a_key_that_can_use_nothing_is_reported_rather_than_returned_empty():
    sender = RecordingSender({"data": []})

    with pytest.raises(ExternalServiceError):
        asyncio.run(list_models(AiProviderConfig(provider="openai", api_key="key"), sender=sender))


def test_listing_requires_the_credential_that_provider_needs():
    with pytest.raises(ValidationServiceError):
        asyncio.run(list_models(AiProviderConfig(provider="openai"), sender=RecordingSender({})))
    # Ollama needs a base URL rather than a key, and says which.
    with pytest.raises(ValidationServiceError):
        asyncio.run(list_models(AiProviderConfig(provider="ollama"), sender=RecordingSender({})))


def test_the_recommendation_is_always_one_of_the_listed_models():
    """The whole point is to stop naming a model the key does not have, so the
    recommendation is picked from the provider's own answer or not at all."""

    # The saved default wins when it is still offered: an existing, working
    # configuration is never quietly moved to something else.
    assert preferred_model(["gemini-2.0-flash", "gemini-2.5-pro"], "gemini-2.0-flash") == "gemini-2.0-flash"
    # Otherwise the cheapest tier the provider itself published.
    assert preferred_model(["gemini-2.5-pro", "gemini-2.5-flash"], "gemini-1.5-flash") == "gemini-2.5-flash"
    # And when no tier hint matches, still a real entry rather than the
    # retired default that caused the problem.
    assert preferred_model(["some-model", "other-model"], "gemini-1.5-flash") == "some-model"
