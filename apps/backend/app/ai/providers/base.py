from typing import Protocol

from app.ai.types import AiProviderConfig, AiProviderResponse, PromptBundle


class AiProvider(Protocol):
    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        ...
