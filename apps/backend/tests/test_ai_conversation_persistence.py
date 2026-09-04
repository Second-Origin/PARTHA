"""AI Workspace conversation persistence (#231).

The AI Workspace previously lost its whole thread on every navigation away
from the page: nothing was ever persisted server-side. These tests drive the
real `/ai/query` and `/ai/conversations` routes end to end, proving both
turns of a query are stored, ordering is preserved across multiple queries,
and the thread is owner- and repository-scoped exactly like every other
`/ai` route.
"""

import io
import zipfile

from app.ai.providers.registry import ProviderRegistry
from app.ai.types import AiProviderConfig, AiProviderResponse, PromptBundle
from app.api.deps import get_provider_registry
from tests.analysis_helpers import run_analysis_jobs


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


class RecordingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        self.calls += 1
        return AiProviderResponse(content=f"answer #{self.calls}")


def _analysed_repository(client, headers: dict, content: bytes = b"export const answer = 42;\n") -> str:
    upload = client.post(
        "/repositories/upload",
        files={
            "file": (
                "sample.zip",
                _zip_bytes({"sample/src/app.ts": content}),
                "application/octet-stream",
            )
        },
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    repository_id = upload.json()["id"]
    assert client.post(f"/analysis/{repository_id}/start", headers=headers).status_code == 200
    assert run_analysis_jobs() == 1
    return repository_id


def _configure_provider(client, headers: dict) -> None:
    response = client.put(
        "/ai/config",
        json={"provider": "openai", "apiKey": "test-key", "model": "test-model"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_conversation_starts_empty_for_a_fresh_repository(auth_client):
    repository_id = _analysed_repository(auth_client, auth_client.headers)

    response = auth_client.get("/ai/conversations", params={"repositoryId": repository_id})

    assert response.status_code == 200
    assert response.json() == {"repositoryId": repository_id, "messages": []}


def test_query_persists_both_turns_in_order_across_multiple_queries(auth_client):
    provider = RecordingProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    auth_client.app.dependency_overrides[get_provider_registry] = lambda: registry

    try:
        repository_id = _analysed_repository(auth_client, auth_client.headers)
        _configure_provider(auth_client, auth_client.headers)

        first = auth_client.post("/ai/query", json={"repositoryId": repository_id, "query": "What is this?"})
        assert first.status_code == 200, first.text
        second = auth_client.post("/ai/query", json={"repositoryId": repository_id, "query": "And then?"})
        assert second.status_code == 200, second.text

        conversation = auth_client.get("/ai/conversations", params={"repositoryId": repository_id})
        assert conversation.status_code == 200
        body = conversation.json()
        assert body["repositoryId"] == repository_id
        messages = body["messages"]

        assert [message["role"] for message in messages] == ["user", "assistant", "user", "assistant"]
        assert [message["content"] for message in messages] == [
            "What is this?",
            "answer #1",
            "And then?",
            "answer #2",
        ]
    finally:
        auth_client.app.dependency_overrides.pop(get_provider_registry, None)


def test_conversation_is_isolated_per_repository(auth_client):
    provider = RecordingProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    auth_client.app.dependency_overrides[get_provider_registry] = lambda: registry

    try:
        first_repository = _analysed_repository(auth_client, auth_client.headers, b"export const first = 1;\n")
        second_repository = _analysed_repository(auth_client, auth_client.headers, b"export const second = 2;\n")
        _configure_provider(auth_client, auth_client.headers)

        assert (
            auth_client.post(
                "/ai/query", json={"repositoryId": first_repository, "query": "About repo one"}
            ).status_code
            == 200
        )
        assert (
            auth_client.post(
                "/ai/query", json={"repositoryId": second_repository, "query": "About repo two"}
            ).status_code
            == 200
        )

        first_thread = auth_client.get("/ai/conversations", params={"repositoryId": first_repository}).json()
        second_thread = auth_client.get("/ai/conversations", params={"repositoryId": second_repository}).json()

        assert [m["content"] for m in first_thread["messages"]] == ["About repo one", "answer #1"]
        assert [m["content"] for m in second_thread["messages"]] == ["About repo two", "answer #2"]
    finally:
        auth_client.app.dependency_overrides.pop(get_provider_registry, None)


def test_conversation_is_owner_scoped_and_returns_404_for_another_owner(client, make_auth_headers):
    alice = make_auth_headers("alice-ai@example.com")
    bob = make_auth_headers("bob-ai@example.com")

    provider = RecordingProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    client.app.dependency_overrides[get_provider_registry] = lambda: registry

    try:
        repository_id = _analysed_repository(client, alice["headers"])
        _configure_provider(client, alice["headers"])
        assert (
            client.post(
                "/ai/query",
                json={"repositoryId": repository_id, "query": "Hello"},
                headers=alice["headers"],
            ).status_code
            == 200
        )
    finally:
        client.app.dependency_overrides.pop(get_provider_registry, None)

    denied = client.get("/ai/conversations", params={"repositoryId": repository_id}, headers=bob["headers"])
    assert denied.status_code == 404

    allowed = client.get("/ai/conversations", params={"repositoryId": repository_id}, headers=alice["headers"])
    assert allowed.status_code == 200
    assert len(allowed.json()["messages"]) == 2


def test_conversation_returns_404_for_an_unknown_repository(auth_client):
    response = auth_client.get(
        "/ai/conversations",
        params={"repositoryId": "11111111-1111-1111-1111-111111111111"},
    )
    assert response.status_code == 404


def test_deleting_repository_removes_its_conversation_turns(auth_client):
    provider = RecordingProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    auth_client.app.dependency_overrides[get_provider_registry] = lambda: registry

    try:
        repository_id = _analysed_repository(auth_client, auth_client.headers)
        _configure_provider(auth_client, auth_client.headers)
        assert (
            auth_client.post("/ai/query", json={"repositoryId": repository_id, "query": "Keep me"}).status_code == 200
        )

        # The conversation turns exist before deletion.
        thread = auth_client.get("/ai/conversations", params={"repositoryId": repository_id})
        assert thread.status_code == 200
        assert len(thread.json()["messages"]) == 2

        # Deleting the repository must cascade to its conversation turns
        # instead of raising a foreign-key violation.
        delete = auth_client.delete(f"/repositories/{repository_id}")
        assert delete.status_code == 204, delete.text

        # The thread is gone with the repository.
        assert auth_client.get("/ai/conversations", params={"repositoryId": repository_id}).status_code == 404
    finally:
        auth_client.app.dependency_overrides.pop(get_provider_registry, None)


def test_concurrent_queries_do_not_interleave_turns(auth_client):
    import threading

    provider = RecordingProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    auth_client.app.dependency_overrides[get_provider_registry] = lambda: registry

    errors: list[Exception] = []
    try:
        repository_id = _analysed_repository(auth_client, auth_client.headers)
        _configure_provider(auth_client, auth_client.headers)

        def fire() -> None:
            try:
                auth_client.post(
                    "/ai/query",
                    json={"repositoryId": repository_id, "query": "Concurrent question"},
                )
            except Exception as exc:  # noqa: BLE001 - surface in the main thread
                errors.append(exc)

        # Fire several queries concurrently. The unique constraint on
        # (owner_id, repository_id, sequence) plus the bounded retry in
        # append_turns must keep every user/assistant pair intact and allocate
        # distinct sequences rather than interleaving or 500-ing.
        threads = [threading.Thread(target=fire) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, [str(e) for e in errors]

        conversation = auth_client.get("/ai/conversations", params={"repositoryId": repository_id})
        assert conversation.status_code == 200
        messages = conversation.json()["messages"]
        # Five queries => ten turns, alternating user/assistant, all distinct
        # sequences (asserted by the DB constraint, surfaced here as ordering).
        assert len(messages) == 10
        roles = [message["role"] for message in messages]
        assert roles == ["user", "assistant"] * 5
    finally:
        auth_client.app.dependency_overrides.pop(get_provider_registry, None)
