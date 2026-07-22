"""Authorization and buffered-SSE behavior for POST /ai/stream (#63, #65, #96).

Regression cover for the defect where ``service.query`` ran inside the SSE
generator, after ``StreamingResponse`` had already emitted 200 headers: a
cross-owner request or a missing provider configuration could only fail
*mid-stream*, so the caller saw a 200 with an empty/aborted body instead of the
required 404 / 422. All failure-prone validation must now run before streaming
starts, so these errors surface as ordinary error responses.
"""

import io
import json
import zipfile

from app.ai.providers.registry import ProviderRegistry
from app.ai.types import AiProviderResponse
from app.api.deps import get_provider_registry
from tests.api_assertions import assert_error_response
from tests.conftest import register_user


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


class _StubProvider:
    async def complete(self, config, prompt) -> AiProviderResponse:
        return AiProviderResponse(content="Two words")


def _upload_repo(client, headers: dict) -> str:
    response = client.post(
        "/repositories/upload",
        files={"file": ("sample.zip", _zip_bytes({"sample/package.json": '{"dependencies":{}}'}), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _configure_provider(client, headers: dict) -> None:
    response = client.put(
        "/ai/config",
        json={"provider": "openai", "apiKey": "sk-test-1234", "model": "gpt-4o-mini"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def _override_registry(client) -> None:
    registry = ProviderRegistry()
    registry.register("openai", _StubProvider())
    client.app.dependency_overrides[get_provider_registry] = lambda: registry


def _parse_events(text: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in text.splitlines() if line.startswith("data: ")]


def _is_event_stream(response) -> bool:
    return "text/event-stream" in response.headers.get("content-type", "")


def test_stream_succeeds_for_owner_with_valid_prerequisites(client):
    auth = register_user(client, "owner@example.com")
    _override_registry(client)
    try:
        repository_id = _upload_repo(client, auth["headers"])
        _configure_provider(client, auth["headers"])

        response = client.post(
            "/ai/stream",
            json={"repositoryId": repository_id, "query": "hi"},
            headers=auth["headers"],
        )

        assert response.status_code == 200
        assert _is_event_stream(response)
        events = _parse_events(response.text)
        assert events[-1] == {"type": "done"}
        content_events = [event for event in events if event["type"] == "content"]
        assert content_events == [{"type": "content", "content": "Two words"}]
    finally:
        client.app.dependency_overrides.pop(get_provider_registry, None)


def test_stream_without_provider_config_returns_clear_error_not_empty_stream(client):
    auth = register_user(client, "noconfig@example.com")
    repository_id = _upload_repo(client, auth["headers"])

    response = client.post(
        "/ai/stream",
        json={"repositoryId": repository_id, "query": "hi"},
        headers=auth["headers"],
    )

    # A clear 422, produced before streaming — not a 200 with an empty stream.
    error = assert_error_response(response, 422, "validation_error")
    assert "not configured" in error.message.lower()
    assert not _is_event_stream(response)


def test_stream_cross_owner_returns_404_before_streaming(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")
    repository_id = _upload_repo(client, alice["headers"])

    response = client.post(
        "/ai/stream",
        json={"repositoryId": repository_id, "query": "hi"},
        headers=bob["headers"],
    )

    # 404, never 200 or 403: a non-owner's request is indistinguishable from a
    # missing repository, and it fails before any stream starts (JSON error body,
    # not an SSE stream).
    assert_error_response(response, 404, "not_found")
    assert not _is_event_stream(response)


def test_stream_requires_authentication(client):
    response = client.post("/ai/stream", json={"repositoryId": "any", "query": "hi"})
    assert_error_response(response, 401, "unauthorized")
