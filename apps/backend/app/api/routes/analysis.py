from fastapi import APIRouter, Depends

from app.api.deps import get_analysis_service, get_current_user
from app.schemas.analysis import AnalysisStartResponse, AnalysisStatusResponse
from app.schemas.architecture import ArchitectureResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.review import EngineeringReviewResponse
from app.services.analysis_service import AnalysisService

# Every analysis route requires auth; records are owner-scoped in AnalysisService.
router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])


@router.post("/{repository_id}/start", response_model=AnalysisStartResponse)
def start_analysis(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisStartResponse:
    return service.start(repository_id)


@router.get("/{repository_id}/status", response_model=AnalysisStatusResponse)
def get_analysis_status(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisStatusResponse:
    return service.status(repository_id)


@router.get("/{repository_id}/architecture", response_model=ArchitectureResponse)
def get_architecture(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> ArchitectureResponse:
    return service.architecture_model(repository_id)


@router.get("/{repository_id}/dependencies", response_model=DependencyGraphResponse)
def get_dependencies(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> DependencyGraphResponse:
    return service.dependency_graph(repository_id)


@router.get("/{repository_id}/review", response_model=EngineeringReviewResponse)
def get_review(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> EngineeringReviewResponse:
    return service.engineering_review(repository_id)
