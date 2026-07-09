import os
from datetime import UTC, datetime

from app.ai.prompt_builder import PromptBuilder
from app.ai.providers.factory import ProviderFactory
from app.ai.repository_context import RepositoryContextBuilder
from app.ai.types import DEFAULT_MODELS, AiProviderConfig, PromptBundle
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationServiceError
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.ai import (
    AiMessage,
    AiProviderPublicConfig,
    AiProviderTestRequest,
    AiProviderTestResponse,
    AiQueryRequest,
    AiQueryResponse,
)


class AiProviderConfigStore:
    def __init__(self, settings: Settings) -> None:
        self.path = settings.storage_path / "ai-provider.json"

    def get_public_config(self) -> AiProviderPublicConfig:
        config = self.read_config()
        if not config:
            return AiProviderPublicConfig()
        return AiProviderPublicConfig(
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            has_api_key=bool(config.api_key),
        )

    def save_config(self, config: AiProviderConfig) -> AiProviderPublicConfig:
        if config.provider != "ollama" and not config.api_key:
            previous = self.read_config()
            if previous and previous.provider == config.provider and previous.api_key:
                config.api_key = previous.api_key
            else:
                raise ValidationServiceError("API key is required for this provider.")

        config.model = config.model or DEFAULT_MODELS[config.provider]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(config.model_dump_json(), encoding="utf-8")
        os.chmod(self.path, 0o600)
        return self.get_public_config()

    def read_config(self) -> AiProviderConfig | None:
        if not self.path.exists():
            return None
        try:
            return AiProviderConfig.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    def config_for_test(self, request: AiProviderTestRequest) -> AiProviderConfig:
        saved = self.read_config()
        provider = request.provider or saved.provider if saved else request.provider
        if not provider:
            raise ValidationServiceError("Choose an AI provider before testing.")
        return AiProviderConfig(
            provider=provider,
            api_key=request.api_key or (saved.api_key if saved and saved.provider == provider else None),
            model=request.model or (saved.model if saved and saved.provider == provider else None) or DEFAULT_MODELS[provider],
            base_url=request.base_url or (saved.base_url if saved and saved.provider == provider else None),
        )


class AiOrchestrator:
    def __init__(
        self,
        repository: RepositoryRepository,
        config_store: AiProviderConfigStore,
        context_builder: RepositoryContextBuilder,
        prompt_builder: PromptBuilder,
        provider_factory: ProviderFactory,
    ) -> None:
        self.repository = repository
        self.config_store = config_store
        self.context_builder = context_builder
        self.prompt_builder = prompt_builder
        self.provider_factory = provider_factory

    def get_config(self) -> AiProviderPublicConfig:
        return self.config_store.get_public_config()

    def save_config(self, config: AiProviderConfig) -> AiProviderPublicConfig:
        return self.config_store.save_config(config)

    async def test_connection(self, request: AiProviderTestRequest) -> AiProviderTestResponse:
        config = self.config_store.config_for_test(request)
        provider = self.provider_factory.resolve(config)
        prompt = PromptBundle(system_prompt="Reply with the single word: ok", user_prompt="Connection test.")
        await provider.complete(config, prompt)
        return AiProviderTestResponse(ok=True, message=f"{config.provider} connection succeeded.", checked_at=datetime.now(UTC))

    async def query(self, request: AiQueryRequest) -> AiQueryResponse:
        record = self.repository.get(request.repository_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": request.repository_id})
        config = self.config_store.read_config()
        if not config:
            raise ValidationServiceError("AI provider is not configured. Open Settings and save a provider first.")

        selected_file = request.context.selected_file if request.context else None
        repository_context = self.context_builder.build(record, selected_file)
        prompt = self.prompt_builder.build(repository_context, request.query)
        provider = self.provider_factory.resolve(config)
        provider_response = await provider.complete(config, prompt)
        return AiQueryResponse(
            message=AiMessage(
                role="assistant",
                content=provider_response.content,
                timestamp=datetime.now(UTC),
                citations=[citation.to_schema() for citation in repository_context.citations],
            ),
            suggestions=[
                "Explain the main architecture boundaries.",
                "What files should I read first?",
                "What are the highest-risk engineering issues?",
            ],
        )
