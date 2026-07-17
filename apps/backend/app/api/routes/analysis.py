from fastapi import APIRouter, Depends

from app.api.deps import get_analysis_service, get_current_user
from app.api.openapi import documented_responses, suppress_automatic_validation_error
from app.schemas.analysis import AnalysisStartResponse, AnalysisStatusResponse
from app.schemas.architecture import ArchitectureResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.review import EngineeringReviewResponse
from app.services.analysis_service import AnalysisService

# Every analysis route requires auth; records are owner-scoped in AnalysisService.
router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])

_REPOSITORY_ID = "11111111-1111-1111-1111-111111111111"
_COMMON_ERRORS = (401, 404, 429, 500)


@router.post(
    "/{repository_id}/start",
    response_model=AnalysisStartResponse,
    responses=documented_responses(
        200,
        "Repository analysis completed synchronously.",
        {"repositoryId": _REPOSITORY_ID, "status": "completed"},
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def start_analysis(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisStartResponse:
    return service.start(repository_id)


@router.get(
    "/{repository_id}/status",
    response_model=AnalysisStatusResponse,
    responses=documented_responses(
        200,
        "Current repository-analysis status.",
        {
            "repositoryId": _REPOSITORY_ID,
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "startedAt": "2026-07-17T00:00:00Z",
            "completedAt": "2026-07-17T00:00:02Z",
            "error": None,
        },
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_analysis_status(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisStatusResponse:
    return service.status(repository_id)


@router.get(
    "/{repository_id}/architecture",
    response_model=ArchitectureResponse,
    responses=documented_responses(
        200,
        "Architecture model derived from repository intelligence.",
        {
            "repositoryId": _REPOSITORY_ID,
            "repositoryName": "example-service",
            "architectureType": "Layered application",
            "detectedLayers": [],
            "nodes": [],
            "edges": [],
            "modules": [],
            "requestFlow": [],
            "summary": {
                "language": "Python",
                "framework": "FastAPI",
                "totalModules": 0,
                "totalNodes": 0,
                "entryPoint": "/app/main.py",
                "architecturePattern": "Layered application",
            },
        },
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_architecture(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> ArchitectureResponse:
    return service.architecture_model(repository_id)


@router.get(
    "/{repository_id}/dependencies",
    response_model=DependencyGraphResponse,
    responses=documented_responses(
        200,
        "Dependency inventory and declared relationships.",
        {
            "repositoryId": _REPOSITORY_ID,
            "nodes": [],
            "edges": [],
            "totalDependencies": 0,
            "vulnerabilityAssessment": {"status": "not_computed"},
            "outdatedAssessment": {"status": "not_computed"},
        },
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_dependencies(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> DependencyGraphResponse:
    return service.dependency_graph(repository_id)


@router.get(
    "/{repository_id}/review",
    response_model=EngineeringReviewResponse,
    responses=documented_responses(
        200,
        "Engineering-review findings and improvement roadmap.",
        {
            "repositoryId": _REPOSITORY_ID,
            "repositoryName": "example-service",
            "generatedAt": "2026-07-17T00:00:00Z",
            "summary": {
                "overallScore": 100,
                "overallTrend": "stable",
                "criticalCount": 0,
                "highCount": 0,
                "mediumCount": 0,
                "lowCount": 0,
                "totalFindings": 0,
            },
            "scores": [],
            "findings": [],
            "roadmap": [],
        },
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_review(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> EngineeringReviewResponse:
    return service.engineering_review(repository_id)
