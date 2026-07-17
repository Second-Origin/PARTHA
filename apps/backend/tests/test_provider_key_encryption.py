"""Encrypted, per-user AI provider keys (E1.5 / #65).

Covers the two contracts the issue calls out: the encrypt/decrypt round-trip,
and the no-leak guarantee — a saved key is stored only as ciphertext, is never
serialised back to the client in full (last-4 only), and one user's key is
neither visible to nor usable by another.
"""

import io
import json
import zipfile

from sqlalchemy import select

from tests.api_assertions import assert_error_response
from tests.conftest import register_user


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload_sample(client, headers: dict) -> str:
    response = client.post(
        "/repositories/upload",
        files={"file": ("sample.zip", _zip_bytes({"sample/package.json": '{"dependencies":{}}'}), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _test_cipher():
    from app.core.config import Settings
    from app.core.crypto import build_provider_cipher

    return build_provider_cipher(Settings(app_env="test"))


# --- cipher --------------------------------------------------------------------


def test_cipher_round_trip_and_ciphertext_differs_from_plaintext():
    cipher = _test_cipher()
    secret = "sk-live-abcdef1234567890"

    token = cipher.encrypt(secret)
    assert token != secret
    assert secret not in token
    assert cipher.decrypt(token) == secret


def test_ciphertext_from_a_different_key_does_not_decrypt():
    import pytest

    from app.core.crypto import InvalidToken, ProviderKeyCipher

    token = _test_cipher().encrypt("sk-secret")
    # A different (valid) Fernet key must not be able to read it.
    other = ProviderKeyCipher(_fresh_key())
    with pytest.raises(InvalidToken):
        other.decrypt(token)


def _fresh_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


# --- no-leak API contract ------------------------------------------------------


def test_ai_config_starts_empty_for_a_new_user(client):
    auth = register_user(client, "empty-config@example.com")

    response = client.get("/ai/config", headers=auth["headers"])

    assert response.status_code == 200
    assert response.json() == {
        "provider": None,
        "model": None,
        "baseUrl": None,
        "hasApiKey": False,
        "apiKeyLast4": None,
    }


def test_saved_key_is_encrypted_at_rest_and_never_returned_in_full(client):
    auth = register_user(client, "keys@example.com")
    save = client.put(
        "/ai/config",
        json={"provider": "openai", "apiKey": "sk-secret-ABCD1234", "model": "gpt-4o-mini"},
        headers=auth["headers"],
    )
    assert save.status_code == 200
    body = save.json()
    assert body["hasApiKey"] is True
    assert body["apiKeyLast4"] == "1234"
    assert "sk-secret-ABCD1234" not in json.dumps(body)

    get_response = client.get("/ai/config", headers=auth["headers"])
    assert get_response.status_code == 200
    got = get_response.json()
    assert got["hasApiKey"] is True
    assert got["apiKeyLast4"] == "1234"
    assert "sk-secret-ABCD1234" not in json.dumps(got)

    # The database column holds ciphertext, never the plaintext key.
    from app.core.database import SessionLocal
    from app.models.ai_provider_config import AiProviderConfigRecord

    db = SessionLocal()
    try:
        record = db.scalars(select(AiProviderConfigRecord)).one()
        assert record.encrypted_api_key
        assert "sk-secret-ABCD1234" not in record.encrypted_api_key
        assert record.api_key_last4 == "1234"
    finally:
        db.close()


def test_store_decrypts_the_owners_key_for_a_request(client):
    auth = register_user(client, "store@example.com")
    client.put(
        "/ai/config",
        json={"provider": "openai", "apiKey": "sk-decrypt-XYZ7"},
        headers=auth["headers"],
    )

    from app.ai.providers.config_store import EncryptedProviderConfigStore
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        store = EncryptedProviderConfigStore(db, _test_cipher(), auth["user"]["id"])
        config = store.read_config()
        # Decrypted in-process, at request time, to talk to the provider.
        assert config is not None
        assert config.provider == "openai"
        assert config.api_key == "sk-decrypt-XYZ7"
    finally:
        db.close()


# --- per-user isolation --------------------------------------------------------


def test_provider_config_is_scoped_per_user(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")

    client.put("/ai/config", json={"provider": "openai", "apiKey": "sk-alice-0001"}, headers=alice["headers"])

    # Bob sees nothing of Alice's.
    bob_config = client.get("/ai/config", headers=bob["headers"]).json()
    assert bob_config["hasApiKey"] is False
    assert bob_config["provider"] is None

    client.put("/ai/config", json={"provider": "anthropic", "apiKey": "sk-bob-9999"}, headers=bob["headers"])

    alice_config = client.get("/ai/config", headers=alice["headers"]).json()
    assert alice_config["provider"] == "openai"
    assert alice_config["apiKeyLast4"] == "0001"

    bob_config = client.get("/ai/config", headers=bob["headers"]).json()
    assert bob_config["provider"] == "anthropic"
    assert bob_config["apiKeyLast4"] == "9999"


# --- missing / carried-forward keys --------------------------------------------


def test_missing_key_for_new_provider_is_a_clear_error(client):
    auth = register_user(client, "missing@example.com")
    response = client.put("/ai/config", json={"provider": "openai"}, headers=auth["headers"])
    error = assert_error_response(response, 422, "validation_error")
    assert "API key is required" in error.message


def test_saving_without_key_carries_the_existing_key_forward(client):
    auth = register_user(client, "carry@example.com")
    client.put(
        "/ai/config",
        json={"provider": "openai", "apiKey": "sk-carry-8888", "model": "gpt-4o-mini"},
        headers=auth["headers"],
    )

    # Re-save with a new model and no key: the stored key is retained.
    response = client.put("/ai/config", json={"provider": "openai", "model": "gpt-4o"}, headers=auth["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["hasApiKey"] is True
    assert body["apiKeyLast4"] == "8888"
    assert body["model"] == "gpt-4o"


def test_ai_query_without_provider_config_returns_a_clear_error(client):
    auth = register_user(client, "noai@example.com")
    repository_id = _upload_sample(client, auth["headers"])

    response = client.post(
        "/ai/query",
        json={"repositoryId": repository_id, "query": "Summarize this repo"},
        headers=auth["headers"],
    )
    error = assert_error_response(response, 422, "validation_error")
    assert "not configured" in error.message.lower()
