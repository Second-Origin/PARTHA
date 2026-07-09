from app.ai.providers.base import AiProvider
from app.schemas.ai import AiProvider as AiProviderName


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[AiProviderName, AiProvider] = {}

    def register(self, provider: AiProviderName, implementation: AiProvider) -> None:
        self._providers[provider] = implementation

    def get(self, provider: AiProviderName) -> AiProvider | None:
        return self._providers.get(provider)
