from app.analysis.architecture import ArchitectureAnalyzer
from app.analysis.authentication import AuthenticationExplanationService
from app.graph.dependency_graph import DependencyGraphBuilder
from app.insights.service import RepositoryInsightsBuilder
from app.repositories.repository_repository import RepositoryRepository
from app.review.review_service import EngineeringReviewBuilder
from app.schemas.architecture import ArchitectureResponse
from app.schemas.authentication import AuthenticationExplanationResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.insights import RepositoryInsightsResponse
from app.schemas.review import EngineeringReviewResponse
from app.core.exceptions import NotFoundError


class AnalysisService:
    """Read-model builder for a repository's persisted analysis (#93).

    Enqueue/status/cancel of the durable analysis lifecycle now live in
    ``AnalysisJobService``; this service only builds the architecture, dependency,
    review, and authentication-explanation read models from already-persisted
    intelligence, which the export service also reuses.
    """

    def __init__(
        self,
        repository: RepositoryRepository,
        architecture: ArchitectureAnalyzer,
        dependencies: DependencyGraphBuilder,
        review: EngineeringReviewBuilder,
        insights: RepositoryInsightsBuilder,
        authentication: AuthenticationExplanationService,
        owner_id: str,
    ) -> None:
        self.repository = repository
        self.architecture = architecture
        self.dependencies = dependencies
        self.review = review
        self.insights = insights
        self.authentication = authentication
        self.owner_id = owner_id

    def architecture_model(self, repository_id: str) -> ArchitectureResponse:
        return self.architecture.build_architecture(self._get_record(repository_id))

    def dependency_graph(self, repository_id: str) -> DependencyGraphResponse:
        return self.dependencies.build(self._get_record(repository_id))

    def engineering_review(self, repository_id: str) -> EngineeringReviewResponse:
        return self.review.build(self._get_record(repository_id))

    def repository_insights(self, repository_id: str) -> RepositoryInsightsResponse:
        return self.insights.build(self._get_record(repository_id))

    def authentication_explanation(self, repository_id: str) -> AuthenticationExplanationResponse:
        return self.authentication.explain(self._get_record(repository_id))

    def _get_record(self, repository_id: str):
        # Owner-scoped: get_for_owner returns None for both a missing repository
        # and one owned by another user, so a cross-user request gets the same
        # 404 as a missing one and never learns the resource exists.
        record = self.repository.get_for_owner(repository_id, self.owner_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": repository_id})
        return record
