"""Static, non-secret setup metadata for each supported AI provider (#291).

This is the one place provider-specific setup facts live. Config validation
(config_store.py), the query-time missing-key guard (orchestrator.py), and
the public capability endpoint the frontend renders its setup guidance from
all read the same PROVIDER_CAPABILITIES entries, so there is exactly one
place to update if a provider's requirements ever change -- never a second
hardcoded provider matrix to keep in sync.

Nothing here is a secret: no API key, provider token, environment value, or
private endpoint. `setup_url` points at each provider's own official,
publicly documented setup/key page -- it is not consulted by, and does not
widen, the server-side egress allowlist in app/core/ai_egress.py; it exists
only for the browser to open in a new tab.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.types import DEFAULT_MODELS
from app.schemas.ai import AiProvider


@dataclass(frozen=True)
class ProviderCapability:
    provider: AiProvider
    display_name: str
    requires_api_key: bool
    requires_base_url: bool
    default_model: str
    setup_url: str
    get_started_hint: str
    support_state: str = "supported"

    def setup_steps(self) -> list[str]:
        """Compose the (at most 4) short setup steps from this provider's facts.

        Only `get_started_hint` is per-provider prose; the remaining steps
        are generated from requires_api_key/requires_base_url/default_model
        so the actual step wording can't drift out of sync with what the
        save/test flow actually requires.
        """

        steps = [self.get_started_hint]
        if self.requires_base_url:
            steps.append("Enter the base URL where it's running.")
        if self.requires_api_key:
            steps.append("Paste in the API key.")
        steps.append(f"Confirm the model ID (default: {self.default_model}).")
        steps.append("Test the connection, then save.")
        return steps


PROVIDER_CAPABILITIES: dict[AiProvider, ProviderCapability] = {
    "openai": ProviderCapability(
        provider="openai",
        display_name="OpenAI",
        requires_api_key=True,
        requires_base_url=False,
        default_model=DEFAULT_MODELS["openai"],
        setup_url="https://platform.openai.com/api-keys",
        get_started_hint="Create an OpenAI account and generate an API key.",
    ),
    "anthropic": ProviderCapability(
        provider="anthropic",
        display_name="Anthropic",
        requires_api_key=True,
        requires_base_url=False,
        default_model=DEFAULT_MODELS["anthropic"],
        setup_url="https://console.anthropic.com/settings/keys",
        get_started_hint="Create an Anthropic account and generate an API key.",
    ),
    "gemini": ProviderCapability(
        provider="gemini",
        display_name="Google Gemini",
        requires_api_key=True,
        requires_base_url=False,
        default_model=DEFAULT_MODELS["gemini"],
        setup_url="https://aistudio.google.com/apikey",
        get_started_hint="Create a Google AI Studio API key.",
    ),
    "openrouter": ProviderCapability(
        provider="openrouter",
        display_name="OpenRouter",
        requires_api_key=True,
        requires_base_url=False,
        default_model=DEFAULT_MODELS["openrouter"],
        setup_url="https://openrouter.ai/keys",
        get_started_hint="Create an OpenRouter account and generate an API key.",
    ),
    "ollama": ProviderCapability(
        provider="ollama",
        display_name="Ollama",
        requires_api_key=False,
        requires_base_url=True,
        default_model=DEFAULT_MODELS["ollama"],
        setup_url="https://ollama.com/download",
        get_started_hint="Install and start Ollama, either locally or on a server you control.",
    ),
}


def capability_for(provider: AiProvider) -> ProviderCapability:
    return PROVIDER_CAPABILITIES[provider]


def all_capabilities() -> list[ProviderCapability]:
    return list(PROVIDER_CAPABILITIES.values())
