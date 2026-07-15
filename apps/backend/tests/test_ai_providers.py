import asyncio
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import httpx
import pytest

from app.ai.orchestrator import AiOrchestrator
from app.ai.prompt_builder import PromptBuilder
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.factory import ProviderFactory
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.legacy import LegacyProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.providers.registry import ProviderRegistry
from app.ai.repository_context import RepositoryContextBuilder
from app.ai.types import AiProviderConfig, PromptBundle
from app.api.deps import get_provider_registry
from app.core.exceptions import ExternalServiceError, ValidationServiceError
from app.schemas.ai import AiProviderTestRequest


PROMPT = PromptBundle(system_prompt="System prompt", user_prompt="User prompt")


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class RecordingAsyncClient:
    calls: list[dict[str, Any]] = []
    payload: dict[str, Any] = {}
    exception: httpx.HTTPError | None = None

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def post(self, url: str, **kwargs):
        self.calls.append({"timeout": self.timeout, "url": url, "kwargs": deepcopy(kwargs)})
        if self.exception:
            raise self.exception
        return FakeResponse(deepcopy(self.payload))


class StaticConfigStore:
    def __init__(self, config: AiProviderConfig) -> None:
        self.config = config

    def config_for_test(self, request: AiProviderTestRequest) -> AiProviderConfig:
        return self.config


def _provider_cases():
    return [
        (
            "openai",
            OpenAIProvider,
            AiProviderConfig(provider="openai", api_key="key"),
            {"choices": [{"message": {"content": "OpenAI answer"}}]},
        ),
        (
            "anthropic",
            AnthropicProvider,
            AiProviderConfig(provider="anthropic", api_key="key"),
            {"content": [{"type": "text", "text": "Anthropic"}, {"type": "tool", "text": "ignored"}, {"type": "text", "text": "answer"}]},
        ),
        (
            "gemini",
            GeminiProvider,
            AiProviderConfig(provider="gemini", api_key="key"),
            {"candidates": [{"content": {"parts": [{"text": "Gemini"}, {"text": "answer"}]}}]},
        ),
        (
            "openrouter",
            OpenRouterProvider,
            AiProviderConfig(provider="openrouter", api_key="key"),
            {"choices": [{"message": {"content": "OpenRouter answer"}}]},
        ),
        (
            "ollama",
            OllamaProvider,
            AiProviderConfig(provider="ollama", base_url="http://localhost:11434/"),
            {"message": {"content": "Ollama answer"}},
        ),
    ]


def _run_with_recording(provider, config: AiProviderConfig, payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch):
    RecordingAsyncClient.calls = []
    RecordingAsyncClient.payload = payload
    RecordingAsyncClient.exception = None
    monkeypatch.setattr(httpx, "AsyncClient", RecordingAsyncClient)
    response = asyncio.run(provider.complete(config, PROMPT))
    return response, deepcopy(RecordingAsyncClient.calls)


def _malformed_payload(provider_name: str) -> dict[str, Any]:
    if provider_name == "anthropic":
        return {"content": None}
    return {}


def _capture_exception(call: Callable[[], Any]) -> Exception:
    try:
        call()
    except Exception as exc:
        return exc
    raise AssertionError("Expected provider call to fail.")


@pytest.mark.parametrize(("provider_name", "provider_class", "config", "payload"), _provider_cases())
def test_dedicated_provider_matches_legacy_success(provider_name, provider_class, config, payload, monkeypatch: pytest.MonkeyPatch):
    legacy_response, legacy_calls = _run_with_recording(LegacyProvider(), config, payload, monkeypatch)
    provider_response, provider_calls = _run_with_recording(provider_class(), config, payload, monkeypatch)

    assert provider_response == legacy_response
    assert provider_calls == legacy_calls
    assert provider_calls[0]["timeout"] == 60


@pytest.mark.parametrize(
    ("provider_name", "provider_class", "config"),
    [
        ("openai", OpenAIProvider, AiProviderConfig(provider="openai")),
        ("anthropic", AnthropicProvider, AiProviderConfig(provider="anthropic")),
        ("gemini", GeminiProvider, AiProviderConfig(provider="gemini")),
        ("openrouter", OpenRouterProvider, AiProviderConfig(provider="openrouter")),
    ],
)
def test_dedicated_provider_matches_legacy_authentication_failure(provider_name, provider_class, config):
    legacy_error = _capture_exception(lambda: asyncio.run(LegacyProvider().complete(config, PROMPT)))
    provider_error = _capture_exception(lambda: asyncio.run(provider_class().complete(config, PROMPT)))

    assert type(provider_error) is type(legacy_error)
    assert isinstance(provider_error, ValidationServiceError)
    assert provider_error.message == legacy_error.message
    assert provider_error.details == legacy_error.details


@pytest.mark.parametrize(("provider_name", "provider_class", "config", "payload"), _provider_cases())
def test_dedicated_provider_matches_legacy_network_failure(provider_name, provider_class, config, payload, monkeypatch: pytest.MonkeyPatch):
    request = httpx.Request("POST", "https://example.test")

    def run(provider):
        RecordingAsyncClient.calls = []
        RecordingAsyncClient.payload = payload
        RecordingAsyncClient.exception = httpx.ConnectError("network failed", request=request)
        monkeypatch.setattr(httpx, "AsyncClient", RecordingAsyncClient)
        return _capture_exception(lambda: asyncio.run(provider.complete(config, PROMPT)))

    legacy_error = run(LegacyProvider())
    provider_error = run(provider_class())

    assert type(provider_error) is type(legacy_error)
    assert isinstance(provider_error, ExternalServiceError)
    assert provider_error.message == legacy_error.message
    assert provider_error.details == legacy_error.details


@pytest.mark.parametrize(("provider_name", "provider_class", "config", "payload"), _provider_cases())
def test_dedicated_provider_matches_legacy_response_parsing_failure(provider_name, provider_class, config, payload, monkeypatch: pytest.MonkeyPatch):
    malformed_payload = _malformed_payload(provider_name)
    legacy_error = _capture_exception(lambda: _run_with_recording(LegacyProvider(), config, malformed_payload, monkeypatch))
    provider_error = _capture_exception(lambda: _run_with_recording(provider_class(), config, malformed_payload, monkeypatch))

    assert type(provider_error) is type(legacy_error)
    assert isinstance(provider_error, ExternalServiceError)
    assert provider_error.message == legacy_error.message
    assert provider_error.details == legacy_error.details


def test_registry_uses_dedicated_providers():
    registry = get_provider_registry()

    assert isinstance(registry.get("openai"), OpenAIProvider)
    assert isinstance(registry.get("anthropic"), AnthropicProvider)
    assert isinstance(registry.get("gemini"), GeminiProvider)
    assert isinstance(registry.get("openrouter"), OpenRouterProvider)
    assert isinstance(registry.get("ollama"), OllamaProvider)
    assert not isinstance(registry.get("openai"), LegacyProvider)


def test_factory_resolves_dedicated_provider():
    registry = ProviderRegistry()
    provider = OpenAIProvider()
    registry.register("openai", provider)

    resolved = ProviderFactory(registry).resolve(AiProviderConfig(provider="openai", api_key="key"))

    assert resolved is provider


def test_connection_testing_uses_resolved_dedicated_provider(monkeypatch: pytest.MonkeyPatch):
    config = AiProviderConfig(provider="openai", api_key="key")
    registry = ProviderRegistry()
    registry.register("openai", OpenAIProvider())
    orchestrator = AiOrchestrator(
        repository=object(),  # type: ignore[arg-type]
        config_store=StaticConfigStore(config),  # type: ignore[arg-type]
        context_builder=RepositoryContextBuilder(object()),  # type: ignore[arg-type]
        prompt_builder=PromptBuilder(),
        provider_factory=ProviderFactory(registry),
        owner_id="owner-1",
    )

    RecordingAsyncClient.calls = []
    RecordingAsyncClient.payload = {"choices": [{"message": {"content": "ok"}}]}
    RecordingAsyncClient.exception = None
    monkeypatch.setattr(httpx, "AsyncClient", RecordingAsyncClient)

    response = asyncio.run(orchestrator.test_connection(AiProviderTestRequest(provider="openai")))

    assert response.ok is True
    assert response.message == "openai connection succeeded."
    assert RecordingAsyncClient.calls[0]["kwargs"]["json"]["messages"] == [
        {"role": "system", "content": "Reply with the single word: ok"},
        {"role": "user", "content": "Connection test."},
    ]
