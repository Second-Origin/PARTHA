"""Deterministic regression coverage for the AI provider egress boundary."""

import asyncio
import io
import logging
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.ai_egress import DestinationPolicyError, ProviderEgressPolicy, normalize_base_url
from app.ai.providers.config_store import EncryptedProviderConfigStore
from app.ai.providers.http import SecureProviderHttpSender, post
from app.ai.providers.ollama import OllamaProvider
from app.ai.types import AiProviderConfig, PromptBundle
from app.core.config import Settings
from app.core.crypto import build_provider_cipher
from app.core.exceptions import ExternalServiceError, ValidationServiceError
from app.core.logging import configure_logging
from app.models.ai_provider_config import AiProviderConfigRecord
from tests.conftest import register_user


PROMPT = PromptBundle(system_prompt="System", user_prompt="Question")
_SELF_HOSTED_BASE = "http://provider.example:11434/approved"
_SELF_HOSTED_CIDR = "203.0.113.0/24"


class MutableResolver:
    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, int]] = []

    def __call__(self, host: str, port: int) -> list[str]:
        self.calls.append((host, port))
        return self.answers


def _self_hosted_policy(resolver: MutableResolver) -> ProviderEgressPolicy:
    return ProviderEgressPolicy(
        mode="self_hosted",
        allowed_base_urls=[_SELF_HOSTED_BASE],
        allowed_cidrs=[_SELF_HOSTED_CIDR],
        resolver=resolver,
    )


def _ollama_config() -> AiProviderConfig:
    return AiProviderConfig(provider="ollama", base_url=_SELF_HOSTED_BASE)


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload_sample(client, headers: dict[str, str]) -> str:
    response = client.post(
        "/repositories/upload",
        files={"file": ("sample.zip", _zip_bytes({"sample/package.json": '{"dependencies":{}}'}), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _insert_unsafe_ollama_config(owner_id: str) -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        db.add(
            AiProviderConfigRecord(
                id=str(uuid4()),
                owner_id=owner_id,
                provider="ollama",
                encrypted_api_key=None,
                api_key_last4=None,
                model="llama3.2",
                base_url="http://unapproved.example:11434",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    finally:
        db.close()


def test_invalid_mode_and_malformed_administrator_allowlists_fail_closed():
    with pytest.raises(ValidationError, match="AI_EGRESS_MODE"):
        Settings(ai_egress_mode="permissive")
    with pytest.raises(ValidationError, match="AI_EGRESS_ALLOWED_BASE_URLS"):
        Settings(ai_egress_allowed_base_urls=["http://user@provider.example"])
    with pytest.raises(ValidationError, match="AI_EGRESS_ALLOWED_CIDRS"):
        Settings(ai_egress_allowed_cidrs=["not-a-cidr"])


def test_base_url_normalization_is_consistent_for_idna_default_port_trailing_dot_and_path():
    normalized = normalize_base_url("HTTPS://exämple.com.:443/approved/")

    assert normalized.base_url == "https://xn--exmple-cua.com/approved"


def test_fixed_providers_reject_tenant_supplied_base_urls_without_dns():
    resolver = MutableResolver(["203.0.113.10"])
    policy = ProviderEgressPolicy(mode="hosted", resolver=resolver)

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(AiProviderConfig(provider="openai", api_key="key", base_url="https://provider.example"))

    assert resolver.calls == []


def test_hosted_mode_rejects_unapproved_custom_destination_before_resolution():
    resolver = MutableResolver(["203.0.113.10"])
    policy = ProviderEgressPolicy(mode="hosted", resolver=resolver)

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(AiProviderConfig(provider="ollama", base_url="https://provider.example"))

    assert resolver.calls == []


@pytest.mark.parametrize(
    "answer",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.10.20",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "100.64.0.1",
        "::1",
        "::",
        "fe80::1",
        "ff02::1",
        "2001:db8::10",
        "::ffff:127.0.0.1",
        "::ffff:224.0.0.1",
        "2606:4700:4700::1111%3",
    ],
)
def test_hosted_mode_rejects_non_public_unicast_ipv4_and_ipv6_answers(answer: str):
    resolver = MutableResolver([answer])
    policy = ProviderEgressPolicy(
        mode="hosted",
        allowed_base_urls=["https://provider.example"],
        resolver=resolver,
    )

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(AiProviderConfig(provider="ollama", base_url="https://provider.example"))


@pytest.mark.parametrize("answer", ["8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"])
def test_hosted_mode_accepts_only_public_unicast_answers_for_an_approved_url(answer: str):
    policy = ProviderEgressPolicy(
        mode="hosted",
        allowed_base_urls=["https://provider.example"],
        resolver=MutableResolver([answer]),
    )

    policy.validate_config(AiProviderConfig(provider="ollama", base_url="https://provider.example"))


def test_self_hosted_exact_approved_base_and_cidr_succeeds():
    resolver = MutableResolver(["203.0.113.10"])
    policy = _self_hosted_policy(resolver)

    policy.validate_config(AiProviderConfig(provider="ollama", base_url=f"{_SELF_HOSTED_BASE}/"))
    prepared = policy.prepare_request(_ollama_config(), f"{_SELF_HOSTED_BASE}/api/chat")

    assert prepared.destination.request_url == f"{_SELF_HOSTED_BASE}/api/chat"
    assert str(prepared.address) == "203.0.113.10"
    assert resolver.calls == [("provider.example", 11434), ("provider.example", 11434)]


@pytest.mark.parametrize("answer", ["127.0.0.1", "::1", "198.51.100.10"])
def test_self_hosted_private_or_local_addresses_require_an_approved_cidr(answer: str):
    resolver = MutableResolver([answer])
    policy = ProviderEgressPolicy(
        mode="self_hosted",
        allowed_base_urls=[_SELF_HOSTED_BASE],
        allowed_cidrs=["192.0.2.0/24"],
        resolver=resolver,
    )

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(_ollama_config())


@pytest.mark.parametrize(
    ("base_url", "answer", "cidr"),
    [
        ("http://localhost:11434", "127.0.0.1", "127.0.0.1/32"),
        ("http://provider.internal:11434", "10.20.30.40", "10.20.30.0/24"),
        ("http://[::1]:11434", "::1", "::1/128"),
        ("http://mapped.internal:11434", "::ffff:127.0.0.1", "::ffff:7f00:0/104"),
    ],
)
def test_self_hosted_explicit_cidr_supports_private_loopback_and_mapped_unicast(
    base_url: str,
    answer: str,
    cidr: str,
):
    policy = ProviderEgressPolicy(
        mode="self_hosted",
        allowed_base_urls=[base_url],
        allowed_cidrs=[cidr],
        resolver=MutableResolver([answer]),
    )

    policy.validate_config(AiProviderConfig(provider="ollama", base_url=base_url))


@pytest.mark.parametrize(
    ("answer", "cidr"),
    [
        ("169.254.10.20", "0.0.0.0/0"),
        ("0.0.0.0", "0.0.0.0/0"),
        ("224.0.0.1", "0.0.0.0/0"),
        ("240.0.0.1", "0.0.0.0/0"),
        ("100.64.0.1", "0.0.0.0/0"),
        ("fe80::1", "::/0"),
        ("::", "::/0"),
        ("ff02::1", "::/0"),
    ],
)
def test_self_hosted_mode_rejects_non_unicast_or_ambiguous_classes_even_with_a_broad_cidr(
    answer: str,
    cidr: str,
):
    policy = ProviderEgressPolicy(
        mode="self_hosted",
        allowed_base_urls=[_SELF_HOSTED_BASE],
        allowed_cidrs=[cidr],
        resolver=MutableResolver([answer]),
    )

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(_ollama_config())


@pytest.mark.parametrize(
    "request_url",
    [
        "https://provider.example:11434/approved/api/chat",
        "http://provider.example:11435/approved/api/chat",
        "http://other.example:11434/approved/api/chat",
        "http://provider.example:11434/not-approved/api/chat",
    ],
)
def test_origin_scheme_port_hostname_and_path_mismatches_are_rejected(request_url: str):
    policy = _self_hosted_policy(MutableResolver(["203.0.113.10"]))

    with pytest.raises(DestinationPolicyError):
        policy.prepare_request(_ollama_config(), request_url)


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "ftp://provider.example",
        "https:///missing-host",
        "http://user@provider.example",
        "http://provider.example/#fragment",
        "http://provider.example#",
        "http://provider.example?",
        "http://2130706433",
        "http://127.1",
        "http://0177.0.0.1",
        "http://0x7f000001",
        "http://provider.example:",
        "http://provider.example:0",
        "http://provider.example:65536",
        "http://provider.example..",
        "http://provider.example/%2fprivate",
        "http://provider.example/approved/../private",
        "http://provider.example/approved//private",
        "http://provider.example\\@other.example",
        "http://provider.example\r\nX-Test: injected",
    ],
)
def test_malformed_and_ambiguous_base_urls_are_rejected(unsafe_url: str):
    policy = ProviderEgressPolicy(mode="hosted", allowed_base_urls=["https://provider.example"])

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(AiProviderConfig(provider="ollama", base_url=unsafe_url))


def test_mixed_dns_answers_fail_closed():
    policy = _self_hosted_policy(MutableResolver(["203.0.113.10", "127.0.0.1"]))

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(_ollama_config())


def test_hosted_mixed_public_and_internal_dns_answers_fail_closed():
    policy = ProviderEgressPolicy(
        mode="hosted",
        allowed_base_urls=["https://provider.example"],
        resolver=MutableResolver(["8.8.8.8", "127.0.0.1"]),
    )

    with pytest.raises(DestinationPolicyError):
        policy.validate_config(AiProviderConfig(provider="ollama", base_url="https://provider.example"))


def test_fixed_cloud_provider_dns_rebinding_is_blocked_even_in_self_hosted_mode():
    policy = ProviderEgressPolicy(
        mode="self_hosted",
        allowed_base_urls=["http://localhost:11434"],
        allowed_cidrs=["127.0.0.1/32"],
        resolver=MutableResolver(["127.0.0.1"]),
    )

    with pytest.raises(DestinationPolicyError):
        policy.prepare_request(
            AiProviderConfig(provider="openai", api_key="key"),
            "https://api.openai.com/v1/chat/completions",
        )


def test_configuration_save_is_validated_before_database_mutation(client):
    auth = register_user(client, "egress-save@example.com")
    response = client.put(
        "/ai/config",
        json={"provider": "ollama", "baseUrl": "http://unapproved.example:11434"},
        headers=auth["headers"],
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert "unapproved.example" not in response.text

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        assert db.scalars(select(AiProviderConfigRecord).where(AiProviderConfigRecord.owner_id == auth["user"]["id"])).first() is None
    finally:
        db.close()


def test_fixed_provider_base_url_is_rejected_without_mutating_a_saved_configuration(client):
    auth = register_user(client, "egress-fixed-save@example.com")
    original = client.put(
        "/ai/config",
        json={"provider": "openai", "apiKey": "sk-unchanged-1234", "model": "gpt-4o-mini"},
        headers=auth["headers"],
    )
    assert original.status_code == 200

    rejected = client.put(
        "/ai/config",
        json={"provider": "openai", "baseUrl": "https://provider.example"},
        headers=auth["headers"],
    )
    assert rejected.status_code == 422
    assert "provider.example" not in rejected.text

    saved = client.get("/ai/config", headers=auth["headers"])
    assert saved.status_code == 200
    assert saved.json()["provider"] == "openai"
    assert saved.json()["model"] == "gpt-4o-mini"
    assert saved.json()["apiKeyLast4"] == "1234"


def test_request_time_dns_recheck_blocks_changed_answer_without_invoking_transport(client):
    auth = register_user(client, "egress-recheck@example.com")
    resolver = MutableResolver(["203.0.113.10"])
    policy = _self_hosted_policy(resolver)

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        store = EncryptedProviderConfigStore(
            db,
            build_provider_cipher(Settings(app_env="test")),
            auth["user"]["id"],
            policy,
        )
        store.save_config(_ollama_config())
        saved = store.read_config()
        assert saved is not None

        calls = 0

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json={"message": {"content": "ok"}})

        resolver.answers = ["127.0.0.1"]
        sender = SecureProviderHttpSender(policy, transport=httpx.MockTransport(handler))
        with pytest.raises(ValidationServiceError, match="destination is not permitted"):
            asyncio.run(OllamaProvider(sender).complete(saved, PROMPT))

        assert calls == 0
    finally:
        db.close()


def test_allowed_dns_answer_is_pinned_to_an_ip_with_original_host_and_sni(monkeypatch):
    resolver = MutableResolver(["8.8.8.8"])
    policy = ProviderEgressPolicy(mode="hosted", resolver=resolver)
    observed: dict[str, object] = {}
    client_options: dict[str, object] = {}
    real_async_client = httpx.AsyncClient

    def recording_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        client_options.update(kwargs)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", recording_client)

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["host"] = request.url.host
        observed["port"] = request.url.port
        observed["host_header"] = request.headers["host"]
        observed["sni"] = request.extensions["sni_hostname"]
        return httpx.Response(200, json={"message": {"content": "ok"}}, request=request)

    sender = SecureProviderHttpSender(policy, transport=httpx.MockTransport(handler))
    config = AiProviderConfig(provider="openai", api_key="key")
    response = asyncio.run(
        sender.post(
            config,
            "https://api.openai.com/v1/chat/completions",
            headers={"Host": "attacker.invalid"},
            json={"model": "example"},
        )
    )

    assert response.status_code == 200
    assert observed == {
        "host": "8.8.8.8",
        "port": None,
        "host_header": "api.openai.com",
        "sni": "api.openai.com",
    }
    assert client_options["verify"] is True
    assert client_options["trust_env"] is False
    assert client_options["follow_redirects"] is False


def test_ipv6_host_header_uses_brackets_and_non_default_port():
    base_url = "http://[::1]:11434"
    policy = ProviderEgressPolicy(
        mode="self_hosted",
        allowed_base_urls=[base_url],
        allowed_cidrs=["::1/128"],
    )
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["host"] = request.headers["host"]
        observed["sni"] = request.extensions["sni_hostname"]
        return httpx.Response(200, json={"message": {"content": "ok"}}, request=request)

    sender = SecureProviderHttpSender(policy, transport=httpx.MockTransport(handler))
    config = AiProviderConfig(provider="ollama", base_url=base_url)
    asyncio.run(sender.post(config, f"{base_url}/api/chat", json={"model": "example"}))

    assert observed == {
        "url": "http://[::1]:11434/api/chat",
        "host": "[::1]:11434",
        "sni": "::1",
    }


def test_production_transport_disables_connection_retries(monkeypatch):
    resolver = MutableResolver(["8.8.8.8"])
    policy = ProviderEgressPolicy(mode="hosted", resolver=resolver)
    options: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    mock_transport = httpx.MockTransport(handler)

    def transport_factory(**kwargs: object) -> httpx.AsyncBaseTransport:
        options.update(kwargs)
        return mock_transport

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", transport_factory)
    sender = SecureProviderHttpSender(policy)
    asyncio.run(
        sender.post(
            AiProviderConfig(provider="openai", api_key="key"),
            "https://api.openai.com/v1/chat/completions",
        )
    )

    assert options == {"verify": True, "retries": 0}
    assert resolver.calls == [("api.openai.com", 443)]


def test_each_request_reresolves_and_uses_a_new_pinned_address():
    resolver = MutableResolver(["203.0.113.10"])
    policy = _self_hosted_policy(resolver)
    destinations: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        destinations.append(request.url.host)
        return httpx.Response(200, json={"message": {"content": "ok"}}, request=request)

    sender = SecureProviderHttpSender(policy, transport=httpx.MockTransport(handler))
    asyncio.run(sender.post(_ollama_config(), f"{_SELF_HOSTED_BASE}/api/chat"))
    resolver.answers = ["203.0.113.11"]
    asyncio.run(sender.post(_ollama_config(), f"{_SELF_HOSTED_BASE}/api/chat"))

    assert destinations == ["203.0.113.10", "203.0.113.11"]
    assert resolver.calls == [("provider.example", 11434), ("provider.example", 11434)]


@pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
def test_redirects_are_not_followed_and_only_one_request_is_sent(status_code: int):
    resolver = MutableResolver(["203.0.113.10"])
    policy = _self_hosted_policy(resolver)
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, headers={"Location": "https://redirected.example"}, request=request)

    sender = SecureProviderHttpSender(policy, transport=httpx.MockTransport(handler))
    with pytest.raises(ExternalServiceError) as caught:
        asyncio.run(post(_ollama_config(), f"{_SELF_HOSTED_BASE}/api/chat", sender=sender, json={"model": "example"}))

    assert caught.value.message == "AI provider request failed."
    assert calls == 1


def test_persisted_unsafe_configuration_and_all_ai_routes_cannot_bypass_policy(client):
    auth = register_user(client, "egress-routes@example.com")
    repository_id = _upload_sample(client, auth["headers"])
    _insert_unsafe_ollama_config(auth["user"]["id"])

    test_response = client.post(
        "/ai/test",
        json={"provider": "ollama", "baseUrl": "http://unapproved.example:11434"},
        headers=auth["headers"],
    )
    assert test_response.status_code == 422

    for path in ("/ai/query", "/ai/stream"):
        response = client.post(path, json={"repositoryId": repository_id, "query": "Summarize"}, headers=auth["headers"])
        assert response.status_code == 422
        assert "unapproved.example" not in response.text


def test_policy_denials_never_include_url_or_resolved_address():
    policy = ProviderEgressPolicy(mode="hosted", allowed_base_urls=["https://provider.example"], resolver=MutableResolver(["127.0.0.1"]))

    with pytest.raises(DestinationPolicyError) as caught:
        policy.validate_config(AiProviderConfig(provider="ollama", base_url="https://provider.example"))

    assert "provider.example" not in str(caught.value)
    assert "127.0.0.1" not in str(caught.value)


def test_provider_http_client_logs_do_not_expose_key_url_or_pinned_address(capsys):
    configure_logging("DEBUG", "text")
    resolver = MutableResolver(["203.0.113.10"])
    policy = _self_hosted_policy(resolver)
    secret = "provider-secret-value"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "ok"}}, request=request)

    sender = SecureProviderHttpSender(policy, transport=httpx.MockTransport(handler))
    asyncio.run(
        sender.post(
            _ollama_config(),
            f"{_SELF_HOSTED_BASE}/api/chat",
            headers={"Authorization": f"Bearer {secret}"},
        )
    )

    output = capsys.readouterr().out
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
    assert secret not in output
    assert "provider.example" not in output
    assert "203.0.113.10" not in output


def test_invalid_secret_header_encoding_is_a_generic_provider_error_without_a_network_call():
    policy = ProviderEgressPolicy(mode="hosted", resolver=MutableResolver(["8.8.8.8"]))
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"ok": True}, request=request)

    sender = SecureProviderHttpSender(policy, transport=httpx.MockTransport(handler))
    config = AiProviderConfig(provider="openai", api_key="invalid-unicode-secret")

    with pytest.raises(ExternalServiceError) as caught:
        asyncio.run(
            post(
                config,
                "https://api.openai.com/v1/chat/completions",
                sender=sender,
                headers={"Authorization": "Bearer \N{SNOWMAN}"},
            )
        )

    assert caught.value.message == "AI provider request failed."
    assert caught.value.details == {"provider": "openai"}
    assert calls == 0
