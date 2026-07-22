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
from app.core.exceptions import ExternalServiceError, ValidationServiceError


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


def test_provider_network_errors_remain_normalized():
    request = httpx.Request("POST", "https://provider.example")
    sender = RecordingSender({}, httpx.ConnectError("network failed", request=request))

    with pytest.raises(ExternalServiceError) as caught:
        asyncio.run(OpenAIProvider(sender).complete(AiProviderConfig(provider="openai", api_key="key"), PROMPT))

    assert caught.value.message == "AI provider request failed."
    assert caught.value.details == {"provider": "openai"}


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
