from app.ai.orchestrator import AiOrchestrator
from app.ai.providers.capabilities import all_capabilities
from app.ai.types import AiProviderConfig
from app.schemas.ai import (
    AiMessage,
    AiProviderCapabilitiesResponse,
    AiProviderCapability,
    AiProviderPublicConfig,
    AiProviderTestRequest,
    AiProviderTestResponse,
    AiQueryRequest,
    AiQueryResponse,
)


class AiService:
    def __init__(self, orchestrator: AiOrchestrator) -> None:
        self.orchestrator = orchestrator

    def list_provider_capabilities(self) -> AiProviderCapabilitiesResponse:
        return AiProviderCapabilitiesResponse(
            providers=[
                AiProviderCapability(
                    provider=capability.provider,
                    display_name=capability.display_name,
                    requires_api_key=capability.requires_api_key,
                    requires_base_url=capability.requires_base_url,
                    default_model=capability.default_model,
                    setup_url=capability.setup_url,
                    setup_steps=capability.setup_steps(),
                    support_state=capability.support_state,
                )
                for capability in all_capabilities()
            ]
        )

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
