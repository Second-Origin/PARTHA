"""Ask each provider which models the caller's key can actually use (#291).

Typing a model ID by hand is where provider setup fails. A default that was
correct when it was written stops being correct -- `gemini-1.5-flash` is not
available to a Google AI Studio project created today -- and the only signal
the user gets is a 400 from the provider, with no way to discover what they
should have typed instead.

Every supported provider publishes its own model list, so nothing here is a
guess: the list is fetched with the user's own key, over the same egress
policy and pinned connection a completion uses, and the caller picks from
what came back.
"""

from __future__ import annotations

from app.ai.providers.http import ProviderHttpSender, get, require_api_key
from app.ai.types import AiProviderConfig
from app.core.exceptions import ExternalServiceError, ValidationServiceError

#: Tier hints, cheapest-and-fastest first. Used only to preselect a sensible
#: entry from a list the provider itself returned -- never to name a model
#: that was not in it.
_PREFERRED_SUBSTRINGS = ("flash-lite", "flash", "mini", "haiku", "small", "turbo")


async def list_models(config: AiProviderConfig, *, sender: ProviderHttpSender | None = None) -> list[str]:
    """Model IDs this configuration can use, sorted, or a plain-language error."""

    lister = _LISTERS.get(config.provider)
    if lister is None:
        raise ValidationServiceError("Unsupported AI provider.", {"provider": config.provider})
    models = await lister(config, sender)
    if not models:
        raise ExternalServiceError(
            "The AI provider returned no usable models for this key.",
            {"provider": config.provider},
        )
    return sorted(set(models))


def preferred_model(models: list[str], default: str) -> str:
    """The entry a first-time user should start on.

    The saved default wins when the provider still offers it, so an existing
    configuration is never quietly moved. Otherwise the cheapest tier whose
    name the provider itself published, and failing that the first entry --
    the point is to land on something that works, not to rank models.
    """

    if default in models:
        return default
    for hint in _PREFERRED_SUBSTRINGS:
        for model in models:
            if hint in model:
                return model
    return models[0]


async def _openai_models(config: AiProviderConfig, sender: ProviderHttpSender | None) -> list[str]:
    require_api_key(config)
    response = await get(
        config,
        "https://api.openai.com/v1/models",
        sender=sender,
        headers={"Authorization": f"Bearer {config.api_key or ''}"},
    )
    return [str(item["id"]) for item in response.json().get("data", []) if item.get("id")]


async def _anthropic_models(config: AiProviderConfig, sender: ProviderHttpSender | None) -> list[str]:
    require_api_key(config)
    response = await get(
        config,
        "https://api.anthropic.com/v1/models?limit=100",
        sender=sender,
        headers={"x-api-key": config.api_key or "", "anthropic-version": "2023-06-01"},
    )
    return [str(item["id"]) for item in response.json().get("data", []) if item.get("id")]


async def _gemini_models(config: AiProviderConfig, sender: ProviderHttpSender | None) -> list[str]:
    require_api_key(config)
    response = await get(
        config,
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
        sender=sender,
        headers={"x-goog-api-key": config.api_key or ""},
    )
    models: list[str] = []
    for item in response.json().get("models", []):
        name = str(item.get("name", ""))
        # Gemini returns "models/<id>" and lists every model the key can see,
        # including embedding-only ones that cannot answer a prompt at all.
        if not name.startswith("models/"):
            continue
        if "generateContent" not in (item.get("supportedGenerationMethods") or []):
            continue
        models.append(name.removeprefix("models/"))
    return models


async def _openrouter_models(config: AiProviderConfig, sender: ProviderHttpSender | None) -> list[str]:
    require_api_key(config)
    response = await get(
        config,
        "https://openrouter.ai/api/v1/models",
        sender=sender,
        headers={"Authorization": f"Bearer {config.api_key or ''}"},
    )
    return [str(item["id"]) for item in response.json().get("data", []) if item.get("id")]


async def _ollama_models(config: AiProviderConfig, sender: ProviderHttpSender | None) -> list[str]:
    base = (config.base_url or "").rstrip("/")
    if not base:
        raise ValidationServiceError("Base URL is required for the selected AI provider.")
    response = await get(config, f"{base}/api/tags", sender=sender)
    return [str(item["name"]) for item in response.json().get("models", []) if item.get("name")]


_LISTERS = {
    "openai": _openai_models,
    "anthropic": _anthropic_models,
    "gemini": _gemini_models,
    "openrouter": _openrouter_models,
    "ollama": _ollama_models,
}
