import asyncio
from copy import deepcopy
from typing import Any

import httpx
import pytest

from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.types import AiProviderConfig, PromptBundle
from app.api.deps import get_provider_registry
from app.core.exceptions import ExternalServiceError, TimeoutServiceError, ValidationServiceError


PROMPT = PromptBundle(system_prompt="System prompt", user_prompt="User prompt")


class RecordingSender:
    def __init__(self, payload: dict[str, Any], error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def post(self, config: AiProviderConfig, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append({"config": config, "url": url, "kwargs": deepcopy(kwargs)})
        if self.error:
            raise self.error
        return httpx.Response(200, json=self.payload, request=httpx.Request("POST", "https://provider.example"))


def _provider_cases():
    return [
        (
            OpenAIProvider,
            AiProviderConfig(provider="openai", api_key="key"),
            {"choices": [{"message": {"content": "OpenAI answer"}}]},
            "https://api.openai.com/v1/chat/completions",
        ),
        (
            AnthropicProvider,
            AiProviderConfig(provider="anthropic", api_key="key"),
            {"content": [{"type": "text", "text": "Anthropic answer"}]},
            "https://api.anthropic.com/v1/messages",
        ),
        (
            GeminiProvider,
            AiProviderConfig(provider="gemini", api_key="key"),
            {"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]},
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        ),
        (
            OpenRouterProvider,
            AiProviderConfig(provider="openrouter", api_key="key"),
            {"choices": [{"message": {"content": "OpenRouter answer"}}]},
            "https://openrouter.ai/api/v1/chat/completions",
        ),
        (
            OllamaProvider,
            AiProviderConfig(provider="ollama", base_url="http://provider.example:11434"),
            {"message": {"content": "Ollama answer"}},
            "http://provider.example:11434/api/chat",
        ),
    ]


@pytest.mark.parametrize(("provider_class", "config", "payload", "expected_url"), _provider_cases())
def test_each_registered_provider_uses_the_injected_central_sender(provider_class, config, payload, expected_url):
    sender = RecordingSender(payload)

    response = asyncio.run(provider_class(sender).complete(config, PROMPT))

    assert response.content.endswith("answer")
    assert len(sender.calls) == 1
    assert sender.calls[0]["url"] == expected_url
    assert sender.calls[0]["config"] is config


def test_gemini_credential_is_sent_in_a_header_not_the_url():
    sender = RecordingSender({"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]})
    key = "gemini-secret-value"

    asyncio.run(GeminiProvider(sender).complete(AiProviderConfig(provider="gemini", api_key=key), PROMPT))

    call = sender.calls[0]
    assert key not in call["url"]
    assert call["kwargs"]["headers"] == {"x-goog-api-key": key}
    assert "params" not in call["kwargs"]


@pytest.mark.parametrize(
    ("provider_class", "config"),
    [
        (OpenAIProvider, AiProviderConfig(provider="openai")),
        (AnthropicProvider, AiProviderConfig(provider="anthropic")),
        (GeminiProvider, AiProviderConfig(provider="gemini")),
        (OpenRouterProvider, AiProviderConfig(provider="openrouter")),
    ],
)
def test_cloud_providers_require_a_key_before_sending(provider_class, config):
    sender = RecordingSender({})

    with pytest.raises(ValidationServiceError, match="API key is required"):
        asyncio.run(provider_class(sender).complete(config, PROMPT))

    assert sender.calls == []


def test_provider_connect_errors_get_an_honest_unreachable_message():
    """#291: "unreachable Ollama" and "invalid base URL" surface identically
    at the connection layer, so one honest message covers both rather than
    guessing which one it was."""

    request = httpx.Request("POST", "https://provider.example")
    sender = RecordingSender({}, httpx.ConnectError("network failed", request=request))

    with pytest.raises(ExternalServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert "Could not reach the AI provider" in caught.value.message
    assert caught.value.details == {"provider": "openai"}


def test_provider_connect_timeout_is_also_reported_as_unreachable():
    """httpx.ConnectTimeout inherits from both ConnectError and
    TimeoutException; a timeout during the connect phase itself should read
    as unreachable, not as "the provider is just slow to answer"."""

    request = httpx.Request("POST", "https://provider.example")
    sender = RecordingSender({}, httpx.ConnectTimeout("connect timed out", request=request))

    with pytest.raises(ExternalServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert "Could not reach the AI provider" in caught.value.message


def test_provider_read_timeout_is_reported_as_a_timeout_not_unreachable():
    request = httpx.Request("POST", "https://provider.example")
    sender = RecordingSender({}, httpx.ReadTimeout("read timed out", request=request))

    with pytest.raises(TimeoutServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert "did not respond in time" in caught.value.message


@pytest.mark.parametrize("status_code", (401, 403))
def test_provider_auth_rejection_explains_the_key_is_the_problem(status_code):
    request = httpx.Request("POST", "https://provider.example")
    response = httpx.Response(status_code, request=request)
    sender = RecordingSender({}, httpx.HTTPStatusError("unauthorized", request=request, response=response))

    with pytest.raises(ValidationServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert "rejected the API key" in caught.value.message


def test_provider_rate_limit_is_explained_in_plain_language():
    request = httpx.Request("POST", "https://provider.example")
    response = httpx.Response(429, request=request)
    sender = RecordingSender({}, httpx.HTTPStatusError("too many requests", request=request, response=response))

    with pytest.raises(ExternalServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert "rate limit" in caught.value.message.lower()


@pytest.mark.parametrize("status_code", (400, 404, 422))
def test_provider_bad_request_is_explained_as_an_unsupported_model(status_code):
    request = httpx.Request("POST", "https://provider.example")
    response = httpx.Response(status_code, request=request)
    sender = RecordingSender({}, httpx.HTTPStatusError("bad request", request=request, response=response))

    with pytest.raises(ValidationServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert "unsupported model" in caught.value.message.lower()


def test_provider_response_parsing_errors_remain_normalized():
    sender = RecordingSender({})

    with pytest.raises(ExternalServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert caught.value.message == "AI provider request failed."


def test_default_registry_contains_only_dedicated_secure_provider_implementations():
    registry = get_provider_registry()

    assert isinstance(registry.get("openai"), OpenAIProvider)
    assert isinstance(registry.get("anthropic"), AnthropicProvider)
    assert isinstance(registry.get("gemini"), GeminiProvider)
    assert isinstance(registry.get("openrouter"), OpenRouterProvider)
    assert isinstance(registry.get("ollama"), OllamaProvider)
