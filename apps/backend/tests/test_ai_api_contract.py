import io
import zipfile

from app.ai.providers.registry import ProviderRegistry
from app.ai.types import AiProviderConfig, AiProviderResponse, PromptBundle
from app.api.deps import get_provider_registry


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


class ContractProvider:
    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        assert config.provider == "openai"
        assert prompt.system_prompt.startswith("You are PARTHA's repository assistant")
        assert prompt.user_prompt == "Summarize this repository"
        return AiProviderResponse(content="Repository summary from test provider.")


def test_ai_query_endpoint_preserves_public_response_contract(auth_client):
    provider = ContractProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    auth_client.app.dependency_overrides[get_provider_registry] = lambda: registry

    try:
        upload_response = auth_client.post(
            "/repositories/upload",
            files={
                "file": (
                    "sample.zip",
                    _zip_bytes(
                        {
                            "sample/package.json": b'{"name":"sample","dependencies":{"react":"^18.0.0"}}',
                            "sample/src/app.ts": b"export const answer = 42;\n",
                        }
                    ),
                    "application/octet-stream",
                )
            },
        )
        assert upload_response.status_code == 201
        repository_id = upload_response.json()["id"]

        config_response = auth_client.put(
            "/ai/config",
            json={"provider": "openai", "apiKey": "test-key", "model": "test-model"},
        )
        assert config_response.status_code == 200

        response = auth_client.post(
            "/ai/query",
            json={
                "repositoryId": repository_id,
                "query": "Summarize this repository",
                "context": {"selectedFile": "/src/app.ts"},
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"message", "suggestions"}
        assert body["suggestions"] == [
            "Explain the main architecture boundaries.",
            "What files should I read first?",
            "What are the highest-risk engineering issues?",
        ]

        message = body["message"]
        assert set(message) == {"role", "content", "timestamp", "citations"}
        assert message["role"] == "assistant"
        assert message["content"] == "Repository summary from test provider."
        assert isinstance(message["timestamp"], str)
        # Fabricated 1:1 placeholder citations were removed (F4/F5). The field is
        # still present in the contract but is null until graph-grounded citations exist.
        assert message["citations"] is None
    finally:
        auth_client.app.dependency_overrides.pop(get_provider_registry, None)
