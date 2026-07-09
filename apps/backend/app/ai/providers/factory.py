from app.ai.providers.base import AiProvider
from app.ai.providers.registry import ProviderRegistry
from app.ai.types import AiProviderConfig
from app.core.exceptions import ValidationServiceError


class ProviderFactory:
    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    def resolve(self, config: AiProviderConfig) -> AiProvider:
        provider = self.registry.get(config.provider)
        if provider is None:
            raise ValidationServiceError("Unsupported AI provider.", {"provider": config.provider})
        return provider
