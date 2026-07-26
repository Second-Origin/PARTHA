from datetime import UTC, datetime

from app.ai.prompt_builder import PromptBuilder
from app.ai.providers.config_store import ProviderConfigStore
from app.ai.providers.factory import ProviderFactory
from app.ai.repository_context import RepositoryContextBuilder
from app.ai.types import PromptBundle
from app.core.exceptions import NotFoundError, ValidationServiceError
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.ai import (
    AiMessage,
    AiProviderConfig,
    AiProviderPublicConfig,
    AiProviderTestRequest,
    AiProviderTestResponse,
    AiQueryRequest,
    AiQueryResponse,
)


class AiOrchestrator:
    def __init__(
        self,
        repository: RepositoryRepository,
        config_store: ProviderConfigStore,
        context_builder: RepositoryContextBuilder,
        prompt_builder: PromptBuilder,
        provider_factory: ProviderFactory,
        owner_id: str,
    ) -> None:
        self.repository = repository
        self.config_store = config_store
        self.context_builder = context_builder
        self.prompt_builder = prompt_builder
        self.provider_factory = provider_factory
        self.owner_id = owner_id

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
        # Owner-scoped: another user's repository id resolves to None and gets
        # the same 404 as a missing one, and the provider config read below is
        # this user's own key — so a query can never run against, or be billed
        # to, someone else's repository or provider.
        record = self.repository.get_for_owner(request.repository_id, self.owner_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": request.repository_id})
        selected_file = request.context.selected_file if request.context else None
        # Resolve the owner-scoped current-revision snapshot before provider
        # configuration or invocation. Missing/stale analysis is a 404, not a
        # misleading provider error.
        repository_context = self.context_builder.build(record, selected_file)
        config = self.config_store.read_config()
        if config is None:
            raise ValidationServiceError("AI provider is not configured. Open Settings and save a provider first.")
        if config.provider != "ollama" and not config.api_key:
            raise ValidationServiceError(
                "AI provider API key is missing. Open Settings and save your provider API key."
            )

        prompt = self.prompt_builder.build(repository_context, request.query)
        provider = self.provider_factory.resolve(config)
        provider_response = await provider.complete(config, prompt)
        return AiQueryResponse(
            message=AiMessage(
                role="assistant",
                content=provider_response.content,
                timestamp=datetime.now(UTC),
                citations=[citation.to_schema() for citation in repository_context.citations] or None,
            ),
            # Suggestions are not computed from the provider response or the
            # repository context yet. Return an explicit empty list instead of
            # presenting generic prompts as analysis-derived recommendations.
            suggestions=[],
        )
