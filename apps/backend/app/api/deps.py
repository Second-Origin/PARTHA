from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.orchestrator import AiOrchestrator
from app.ai.prompt_builder import PromptBuilder
from app.ai.providers.config_store import EncryptedProviderConfigStore
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.factory import ProviderFactory
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.providers.registry import ProviderRegistry
from app.ai.repository_context import RepositoryContextBuilder
from app.analysis.architecture import ArchitectureAnalyzer
from app.auth.security import decode_access_token
from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.core.crypto import ProviderKeyCipher, build_provider_cipher
from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.github.client import GitHubClient
from app.graph.dependency_graph import DependencyGraphBuilder
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.intelligence.query_service import SnapshotQueryService
from app.models.user import User
from app.parsers.repository_parser import RepositoryParser
from app.repositories.repository_repository import RepositoryRepository
from app.reports.export_service import ExportService
from app.review.review_service import EngineeringReviewBuilder
from app.services.ai_service import AiService
from app.services.analysis_service import AnalysisService
from app.services.documentation_service import DocumentationService
from app.services.repository_service import RepositoryService
from app.storage.local import LocalStorage


def get_repository_repository(db: Session = Depends(get_db)) -> RepositoryRepository:
    return RepositoryRepository(db)


_bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(db, settings)


def _user_from_bearer(token: str, db: Session, settings: Settings) -> User:
    user_id = decode_access_token(token, settings)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired access token.")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Require a valid Bearer access token and return its user (401 otherwise)."""
    if credentials is None:
        raise UnauthorizedError("Not authenticated.")
    return _user_from_bearer(credentials.credentials, db, settings)


def get_local_storage(settings: Settings = Depends(get_settings)) -> LocalStorage:
    return LocalStorage(settings)


def get_github_client(settings: Settings = Depends(get_settings)) -> GitHubClient:
    return GitHubClient(settings)


def get_repository_parser() -> RepositoryParser:
    return RepositoryParser()


def get_repository_intelligence_engine() -> RepositoryIntelligenceEngine:
    return RepositoryIntelligenceEngine()


def get_snapshot_query_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SnapshotQueryService:
    return SnapshotQueryService(db, current_user.id)


def get_repository_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    storage: LocalStorage = Depends(get_local_storage),
    github: GitHubClient = Depends(get_github_client),
    parser: RepositoryParser = Depends(get_repository_parser),
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> RepositoryService:
    return RepositoryService(
        repository=repository,
        storage=storage,
        github=github,
        parser=parser,
        intelligence=intelligence,
        settings=settings,
        owner_id=current_user.id,
    )


def get_architecture_analyzer(
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
    snapshots: SnapshotQueryService = Depends(get_snapshot_query_service),
) -> ArchitectureAnalyzer:
    return ArchitectureAnalyzer(intelligence, snapshots)


def get_dependency_graph_builder(
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> DependencyGraphBuilder:
    return DependencyGraphBuilder(intelligence)


def get_engineering_review_builder(
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> EngineeringReviewBuilder:
    return EngineeringReviewBuilder(intelligence)


def get_provider_cipher(settings: Settings = Depends(get_settings)) -> ProviderKeyCipher:
    return build_provider_cipher(settings)


def get_ai_config_store(
    db: Session = Depends(get_db),
    cipher: ProviderKeyCipher = Depends(get_provider_cipher),
    current_user: User = Depends(get_current_user),
) -> EncryptedProviderConfigStore:
    return EncryptedProviderConfigStore(db, cipher, current_user.id)


def get_repository_context_builder(
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> RepositoryContextBuilder:
    return RepositoryContextBuilder(intelligence)


def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()


def get_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register("openai", OpenAIProvider())
    registry.register("anthropic", AnthropicProvider())
    registry.register("gemini", GeminiProvider())
    registry.register("openrouter", OpenRouterProvider())
    registry.register("ollama", OllamaProvider())
    return registry


def get_provider_factory(
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> ProviderFactory:
    return ProviderFactory(registry)


def get_analysis_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    architecture: ArchitectureAnalyzer = Depends(get_architecture_analyzer),
    dependencies: DependencyGraphBuilder = Depends(get_dependency_graph_builder),
    review: EngineeringReviewBuilder = Depends(get_engineering_review_builder),
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
    current_user: User = Depends(get_current_user),
) -> AnalysisService:
    return AnalysisService(
        repository=repository,
        architecture=architecture,
        dependencies=dependencies,
        review=review,
        intelligence=intelligence,
        owner_id=current_user.id,
    )


def get_ai_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    config_store: EncryptedProviderConfigStore = Depends(get_ai_config_store),
    context_builder: RepositoryContextBuilder = Depends(get_repository_context_builder),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
    provider_factory: ProviderFactory = Depends(get_provider_factory),
    current_user: User = Depends(get_current_user),
) -> AiService:
    orchestrator = AiOrchestrator(
        repository=repository,
        config_store=config_store,
        context_builder=context_builder,
        prompt_builder=prompt_builder,
        provider_factory=provider_factory,
        owner_id=current_user.id,
    )
    return AiService(orchestrator)


def get_documentation_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    architecture: ArchitectureAnalyzer = Depends(get_architecture_analyzer),
    dependencies: DependencyGraphBuilder = Depends(get_dependency_graph_builder),
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
    current_user: User = Depends(get_current_user),
) -> DocumentationService:
    return DocumentationService(
        repository=repository,
        architecture=architecture,
        dependencies=dependencies,
        intelligence=intelligence,
        owner_id=current_user.id,
    )


def get_export_service(
    analysis: AnalysisService = Depends(get_analysis_service),
    documentation: DocumentationService = Depends(get_documentation_service),
) -> ExportService:
    return ExportService(analysis=analysis, documentation=documentation)
