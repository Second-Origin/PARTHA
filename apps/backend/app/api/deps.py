from fastapi import Depends
from sqlalchemy.orm import Session

from app.analysis.architecture import ArchitectureAnalyzer
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.github.client import GitHubClient
from app.graph.dependency_graph import DependencyGraphBuilder
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.parsers.repository_parser import RepositoryParser
from app.repositories.repository_repository import RepositoryRepository
from app.review.review_service import EngineeringReviewBuilder
from app.services.ai_service import AiService
from app.services.analysis_service import AnalysisService
from app.services.documentation_service import DocumentationService
from app.services.repository_service import RepositoryService
from app.storage.local import LocalStorage


def get_repository_repository(db: Session = Depends(get_db)) -> RepositoryRepository:
    return RepositoryRepository(db)


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
) -> RepositoryService:
    return RepositoryService(
        repository=repository,
        storage=storage,
        github=github,
        parser=parser,
        intelligence=intelligence,
        settings=settings,
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
    settings: Settings = Depends(get_settings),
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> AiService:
    return AiService(repository=repository, settings=settings, intelligence=intelligence)


def get_documentation_service(
    repository: RepositoryRepository = Depends(get_repository_repository),
    architecture: ArchitectureAnalyzer = Depends(get_architecture_analyzer),
    dependencies: DependencyGraphBuilder = Depends(get_dependency_graph_builder),
    intelligence: RepositoryIntelligenceEngine = Depends(get_repository_intelligence_engine),
) -> DocumentationService:
    return DocumentationService(repository=repository, architecture=architecture, dependencies=dependencies, intelligence=intelligence)
