"""GET /ai/providers: safe, non-secret setup metadata (#291).

Covers the acceptance criteria that matter most: the response never leaks a
secret, it's auth-gated like every other /ai/* route, and its facts actually
agree with what the save/test flow enforces -- the whole point of a single
registry is that these two things cannot silently drift apart.
"""

import re

import pytest

from app.ai.providers.capabilities import PROVIDER_CAPABILITIES, capability_for
from tests.conftest import register_user


def test_list_providers_requires_authentication(client):
    response = client.get("/ai/providers")

    assert response.status_code == 401


def test_list_providers_returns_every_supported_provider_with_the_expected_shape(auth_client):
    response = auth_client.get("/ai/providers")

    assert response.status_code == 200, response.text
    body = response.json()
    providers = {item["provider"]: item for item in body["providers"]}
    assert set(providers) == set(PROVIDER_CAPABILITIES)

    for provider_id, item in providers.items():
        capability = capability_for(provider_id)
        assert item["displayName"] == capability.display_name
        assert item["requiresApiKey"] == capability.requires_api_key
        assert item["requiresBaseUrl"] == capability.requires_base_url
        assert item["defaultModel"] == capability.default_model
        assert item["setupUrl"] == capability.setup_url
        assert item["supportState"] == "supported"
        # At most 4 short steps, matching the issue's own UI constraint.
        assert 1 <= len(item["setupSteps"]) <= 4
        assert all(isinstance(step, str) and step for step in item["setupSteps"])


def test_list_providers_setup_urls_are_https_and_point_at_the_providers_own_domain(auth_client):
    response = auth_client.get("/ai/providers")
    providers = {item["provider"]: item["setupUrl"] for item in response.json()["providers"]}

    expected_hosts = {
        "openai": "platform.openai.com",
        "anthropic": "console.anthropic.com",
        "gemini": "aistudio.google.com",
        "openrouter": "openrouter.ai",
        "ollama": "ollama.com",
    }
    for provider_id, expected_host in expected_hosts.items():
        url = providers[provider_id]
        assert url.startswith("https://"), f"{provider_id} setup URL must be HTTPS: {url}"
        assert expected_host in url, f"{provider_id} setup URL must point at {expected_host}: {url}"


def test_list_providers_response_carries_no_secret_looking_material(auth_client):
    """The schema legitimately has fields *about* keys (requiresApiKey) --
    what must never appear is an actual key-shaped value."""

    response = auth_client.get("/ai/providers")
    serialized = response.text

    assert not re.search(r"sk-[A-Za-z0-9]{10,}", serialized)
    # Every string value in the payload is either a known short label/URL/
    # step sentence, or a boolean/provider id -- assert none of them is a
    # long opaque token, which is what a real leaked credential would look
    # like regardless of which field carried it.
    for item in response.json()["providers"]:
        for value in item.values():
            if isinstance(value, str):
                assert not re.fullmatch(r"[A-Za-z0-9_-]{24,}", value), f"looks like a token: {value!r}"


def _config_store(db, owner_id: str):
    """A store wired with an egress policy that always allows, so these
    tests exercise only the capability-driven key requirement -- egress/SSRF
    policy has its own dedicated coverage in test_ai_egress_policy.py."""

    from app.ai.providers.config_store import EncryptedProviderConfigStore
    from app.core.crypto import build_provider_cipher
    from app.core.config import Settings

    class _AllowAllEgressPolicy:
        def validate_config(self, config):  # noqa: ANN001, ANN201 -- test stub
            return None

    return EncryptedProviderConfigStore(
        db=db,
        cipher=build_provider_cipher(Settings(app_env="test")),
        owner_id=owner_id,
        egress_policy=_AllowAllEgressPolicy(),
    )


def test_ollama_capability_matches_actual_save_time_enforcement(client):
    """The registry says ollama doesn't require a key; prove the store
    actually behaves that way, so the two can't silently diverge."""

    from app.ai.types import AiProviderConfig
    from app.core.database import SessionLocal

    assert capability_for("ollama").requires_api_key is False
    owner_id = register_user(client, "ollama-capability@example.com")["user"]["id"]

    with SessionLocal() as db:
        store = _config_store(db, owner_id)
        result = store.save_config(AiProviderConfig(provider="ollama", base_url="http://provider.example:11434"))

    assert result.has_api_key is False
    assert result.provider == "ollama"


def test_cloud_provider_capability_matches_actual_save_time_enforcement(client):
    """The registry says openai requires a key; prove the store actually
    rejects saving one without it."""

    from app.ai.types import AiProviderConfig
    from app.core.database import SessionLocal
    from app.core.exceptions import ValidationServiceError

    assert capability_for("openai").requires_api_key is True
    owner_id = register_user(client, "openai-capability@example.com")["user"]["id"]

    with SessionLocal() as db, pytest.raises(ValidationServiceError, match="API key is required"):
        _config_store(db, owner_id).save_config(AiProviderConfig(provider="openai"))
