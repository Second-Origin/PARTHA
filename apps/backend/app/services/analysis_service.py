from datetime import UTC, datetime

from app.analysis.architecture import ArchitectureAnalyzer
from app.graph.dependency_graph import DependencyGraphBuilder
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.repositories.repository_repository import RepositoryRepository
from app.review.review_service import EngineeringReviewBuilder
from app.schemas.analysis import AnalysisStartResponse, AnalysisStatusResponse
from app.schemas.architecture import ArchitectureResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.review import EngineeringReviewResponse
from app.core.exceptions import NotFoundError, ServiceError


class AnalysisService:
    def __init__(
        self,
        repository: RepositoryRepository,
        architecture: ArchitectureAnalyzer,
        dependencies: DependencyGraphBuilder,
        review: EngineeringReviewBuilder,
        intelligence: RepositoryIntelligenceEngine,
    ) -> None:
        self.repository = repository
        self.architecture = architecture
        self.dependencies = dependencies
        self.review = review
        self.intelligence = intelligence

    def start(self, repository_id: str) -> AnalysisStartResponse:
        record = self._get_record(repository_id)
        if record.status == "completed":
            return AnalysisStartResponse(repository_id=record.id, status="completed")
        if record.status == "error":
            return AnalysisStartResponse(repository_id=record.id, status="failed")

        record.status = "analysing"
        record.analysis_stage = "preparing-architecture"
        record.analysis_progress = 80
        self.repository.save(record)
        try:
            repository_intelligence = self.intelligence.from_record(record)
            self.intelligence.persist(record, repository_intelligence)
            self.repository.save(record)
            self.architecture.build_architecture(record)
            self.dependencies.build(record)
            self.review.build(record)
        except Exception as exc:
            record.status = "error"
            record.analysis_stage = None
            record.analysis_progress = 0
            record.error_message = "Repository analysis failed."
            self.repository.save(record)
            raise ServiceError("Repository analysis failed.", {"repositoryId": record.id}) from exc

        record.status = "completed"
        record.analysis_stage = "completed"
        record.analysis_progress = 100
        record.error_message = None
        record.analysed_at = datetime.now(UTC)
        self.repository.save(record)
        return AnalysisStartResponse(repository_id=record.id, status="completed")

    def status(self, repository_id: str) -> AnalysisStatusResponse:
        record = self._get_record(repository_id)
        status = "failed" if record.status == "error" else "completed" if record.status == "completed" else "processing"
        return AnalysisStatusResponse(
            repository_id=record.id,
            status=status,
            stage=record.analysis_stage,
            progress=record.analysis_progress,
            started_at=record.uploaded_at,
            completed_at=record.analysed_at,
            error=record.error_message,
        )

    def architecture_model(self, repository_id: str) -> ArchitectureResponse:
        return self.architecture.build_architecture(self._get_record(repository_id))

    def dependency_graph(self, repository_id: str) -> DependencyGraphResponse:
        return self.dependencies.build(self._get_record(repository_id))

    def engineering_review(self, repository_id: str) -> EngineeringReviewResponse:
        return self.review.build(self._get_record(repository_id))

    def _get_record(self, repository_id: str):
        record = self.repository.get(repository_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": repository_id})
        return record
