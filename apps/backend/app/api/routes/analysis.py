from fastapi import APIRouter, Depends

from app.api.deps import get_analysis_job_service, get_analysis_service, get_current_user
from app.api.openapi import documented_responses, suppress_automatic_validation_error
from app.models.analysis_job import AnalysisJob
from app.schemas.analysis import AnalysisStartResponse, AnalysisStatusResponse
from app.schemas.architecture import ArchitectureResponse
from app.schemas.authentication import AuthenticationExplanationResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.review import EngineeringReviewResponse
from app.services.analysis_job_service import AnalysisJobService
from app.services.analysis_service import AnalysisService

# Every analysis route requires auth; records are owner-scoped in the services.
router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])

_REPOSITORY_ID = "11111111-1111-1111-1111-111111111111"
_JOB_ID = "22222222-2222-2222-2222-222222222222"
_COMMON_ERRORS = (401, 404, 429, 500)
_CANCEL_ERRORS = (401, 404, 409, 429, 500)
_REVIEW_ERRORS = (401, 404, 409, 429, 500)


def _status_response(repository_id: str, job: AnalysisJob | None) -> AnalysisStatusResponse:
    """Map the durable job row to the status contract.

    A missing job means analysis has never been submitted; the route surfaces
    that as ``queued`` with zero progress rather than inventing a separate
    "not started" state.
    """

    if job is None:
        return AnalysisStatusResponse(repository_id=repository_id, status="queued", progress=0)
    return AnalysisStatusResponse(
        repository_id=repository_id,
        status=job.status,
        job_id=job.id,
        stage=job.stage,
        progress=job.progress,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error_message,
    )


@router.post(
    "/{repository_id}/start",
    response_model=AnalysisStartResponse,
    responses=documented_responses(
        200,
        "Analysis was durably enqueued (or already complete); the request never blocks on the worker.",
        {"repositoryId": _REPOSITORY_ID, "status": "queued", "jobId": _JOB_ID},
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def start_analysis(
    repository_id: str,
    service: AnalysisJobService = Depends(get_analysis_job_service),
) -> AnalysisStartResponse:
    job = service.submit(repository_id)
    return AnalysisStartResponse(repository_id=job.repository_id, status=job.status, job_id=job.id)


@router.get(
    "/{repository_id}/status",
    response_model=AnalysisStatusResponse,
    responses=documented_responses(
        200,
        "Current durable analysis-job status.",
        {
            "repositoryId": _REPOSITORY_ID,
            "status": "completed",
            "jobId": _JOB_ID,
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
    service: AnalysisJobService = Depends(get_analysis_job_service),
) -> AnalysisStatusResponse:
    return _status_response(repository_id, service.status(repository_id))


@router.post(
    "/{repository_id}/cancel",
    response_model=AnalysisStatusResponse,
    responses=documented_responses(
        200,
        "Analysis cancellation was accepted; a running job is cancelled cooperatively.",
        {
            "repositoryId": _REPOSITORY_ID,
            "status": "cancelled",
            "jobId": _JOB_ID,
            "stage": None,
            "progress": 0,
            "startedAt": None,
            "completedAt": "2026-07-17T00:00:01Z",
            "error": None,
        },
        *_CANCEL_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def cancel_analysis(
    repository_id: str,
    service: AnalysisJobService = Depends(get_analysis_job_service),
) -> AnalysisStatusResponse:
    return _status_response(repository_id, service.cancel(repository_id))


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
            "relationshipSnapshotId": None,
            "diagnostics": [
                {
                    "code": "ARCH-REL-NOT-EXTRACTED",
                    "category": "relationship extraction",
                    "severity": "info",
                    "message": "No sealed repository-intelligence snapshot is available for relationship analysis.",
                }
            ],
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
    "/{repository_id}/architecture/authentication",
    response_model=AuthenticationExplanationResponse,
    responses=documented_responses(
        200,
        "Evidence-backed explanation of how authentication works, read exclusively "
        "from the sealed Repository Intelligence snapshot query layer.",
        {
            "schemaVersion": "auth-explanation.v1",
            "repositoryId": _REPOSITORY_ID,
            "repositoryName": "example-service",
            "revisionKind": "upload",
            "revisionValue": "sha256:" + "0" * 64,
            "snapshotId": "snap_example",
            "status": "ready",
            "summary": (
                "Found 1 authentication-relevant route(s), 1 middleware/guard dependency(ies), "
                "1 service(s), and 1 model(s), each backed by a citation to its exact stored source span."
            ),
            "claims": [
                {
                    "kind": "route",
                    "name": "/me",
                    "confidence": "observed",
                    "evidence": [
                        {
                            "snapshotId": "snap_example",
                            "factId": "src/routes.py::(anonymous:route#1)",
                            "path": "src/routes.py",
                            "startLine": 10,
                            "endLine": 10,
                        }
                    ],
                }
            ],
            "relationships": [],
            "diagnostics": [],
        },
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_authentication_explanation(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AuthenticationExplanationResponse:
    return service.authentication_explanation(repository_id)


@router.get(
    "/{repository_id}/dependencies",
    response_model=DependencyGraphResponse,
    responses=documented_responses(
        200,
        "Dependency inventory and declared relationships.",
        {
            "repositoryId": _REPOSITORY_ID,
            "nodes": [
                {
                    "id": "dependency:npm:react",
                    "name": "react",
                    "version": "^18.3.0",
                    "type": "production",
                    "ecosystem": "npm",
                    "declarations": [
                        {
                            "name": "react",
                            "manifestPath": "apps/frontend/package.json",
                            "workspacePath": "apps/frontend",
                            "startLine": 3,
                            "endLine": 3,
                            "extractor": "dependency-manifest",
                            "extractorVersion": "1.2.0",
                            "ecosystem": "npm",
                            "version": "^18.3.0",
                            "type": "production",
                        }
                    ],
                    "size": None,
                }
            ],
            "edges": [],
            "totalDependencies": 1,
            "manifestCount": 1,
            "diagnostics": [],
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
        "Computed engineering-review findings and roadmap; pending analysis returns 409.",
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
        *_REVIEW_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_review(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> EngineeringReviewResponse:
    return service.engineering_review(repository_id)
