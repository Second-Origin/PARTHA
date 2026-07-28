from app.ai.orchestrator import AiOrchestrator
from app.ai.types import AiProviderConfig
from app.schemas.ai import (
    AiMessage,
    AiProviderPublicConfig,
    AiProviderTestRequest,
    AiProviderTestResponse,
    AiQueryRequest,
    AiQueryResponse,
)


class AiService:
    def __init__(self, orchestrator: AiOrchestrator) -> None:
        self.orchestrator = orchestrator

    def get_config(self) -> AiProviderPublicConfig:
        return self.orchestrator.get_config()

    def save_config(self, config: AiProviderConfig) -> AiProviderPublicConfig:
        return self.orchestrator.save_config(config)

    async def test_connection(self, request: AiProviderTestRequest) -> AiProviderTestResponse:
        return await self.orchestrator.test_connection(request)

    async def query(self, request: AiQueryRequest) -> AiQueryResponse:
        return await self.orchestrator.query(request)

    def list_conversation(self, repository_id: str) -> list[AiMessage]:
        return self.orchestrator.list_conversation(repository_id)
