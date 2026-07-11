from uuid import uuid4

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.orchestrator import AiOrchestrator, AiProviderConfigStore
from app.ai.prompt_builder import PromptBuilder
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
from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.github.client import GitHubClient
from app.graph.dependency_graph import DependencyGraphBuilder
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.user import SEED_USER_EMAIL, SEED_USER_ID, User
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


def _ensure_seed_user(db: Session) -> User:
    user = db.get(User, SEED_USER_ID)
    if user is None:
        user = User(id=SEED_USER_ID, email=SEED_USER_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _resolve_dev_user(db: Session, email: str) -> User:
    normalized = email.strip().lower()
    user = db.scalars(select(User).where(User.email == normalized)).first()
    if user is None:
        user = User(id=str(uuid4()), email=normalized)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


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


def get_current_user_or_default(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_dev_user: str | None = Header(default=None, alias="X-Dev-User"),
) -> User:
    """Resolve the user for routes that still tolerate anonymous access.

    A presented Bearer token is always validated strictly — sending a bad
    token is an authentication attempt and gets a 401, never a silent
    fallback. Without a token, the temporary pre-auth behaviour applies: the
    ``X-Dev-User`` header selects a user in development/test, and everything
    else is attributed to the seed user. E1.3 deletes this fallback (and the
    header) once the frontend can sign in, leaving only ``get_current_user``.
    """
    if credentials is not None:
        return _user_from_bearer(credentials.credentials, db, settings)
    if x_dev_user and settings.app_env in {"development", "test"}:
        return _resolve_dev_user(db, x_dev_user)
    return _ensure_seed_user(db)


def get_local_storage(settings: Settings = Depends(get_settings)) -> LocalStorage:
    return LocalStorage(settings)


def get_github_client(settings: Settings = Depends(get_settings)) -> GitHubClient:
    return GitHubClient(settings)


def get_repository_parser() -> RepositoryParser:
    return RepositoryParser()


def get_repository_intelligence_engine() -> RepositoryIntelligenceEngine:
    return RepositoryIntelligenceEngine()


def get_repository_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    storage: LocalStorage = Depends(get_local_storage),
    github: GitHubClient = Depends(get_github_client),
    parser: RepositoryParser = Depends(get_repository_parser),
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user_or_default),
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
) -> ArchitectureAnalyzer:
    return ArchitectureAnalyzer(intelligence)


def get_dependency_graph_builder(
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> DependencyGraphBuilder:
    return DependencyGraphBuilder(intelligence)


def get_engineering_review_builder(
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> EngineeringReviewBuilder:
    return EngineeringReviewBuilder(intelligence)


def get_ai_config_store(settings: Settings = Depends(get_settings)) -> AiProviderConfigStore:
    return AiProviderConfigStore(settings)


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
) -> AnalysisService:
    return AnalysisService(
        repository=repository,
        architecture=architecture,
        dependencies=dependencies,
        review=review,
        intelligence=intelligence,
    )


def get_ai_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    config_store: AiProviderConfigStore = Depends(get_ai_config_store),
    context_builder: RepositoryContextBuilder = Depends(get_repository_context_builder),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
    provider_factory: ProviderFactory = Depends(get_provider_factory),
) -> AiService:
    orchestrator = AiOrchestrator(
        repository=repository,
        config_store=config_store,
        context_builder=context_builder,
        prompt_builder=prompt_builder,
        provider_factory=provider_factory,
    )
    return AiService(orchestrator)


def get_documentation_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    architecture: ArchitectureAnalyzer = Depends(get_architecture_analyzer),
    dependencies: DependencyGraphBuilder = Depends(get_dependency_graph_builder),
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> DocumentationService:
    return DocumentationService(repository=repository, architecture=architecture, dependencies=dependencies, intelligence=intelligence)


def get_export_service(
    analysis: AnalysisService = Depends(get_analysis_service),
    documentation: DocumentationService = Depends(get_documentation_service),
) -> ExportService:
    return ExportService(analysis=analysis, documentation=documentation)
