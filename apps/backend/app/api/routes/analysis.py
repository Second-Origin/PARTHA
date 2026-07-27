from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_analysis_job_service,
    get_analysis_service,
    get_current_user,
    get_evidence_source_service,
    require_repository_owner,
    get_revision_manifest_service,
)
from app.api.openapi import documented_responses, suppress_automatic_validation_error
from app.models.analysis_job import AnalysisJob
from app.schemas.analysis import AnalysisStartResponse, AnalysisStatusResponse
from app.schemas.architecture import ArchitectureResponse
from app.schemas.authentication import AuthenticationExplanationResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.evidence import EvidenceSourceResponse
from app.schemas.insights import RepositoryInsightsResponse
from app.schemas.manifest import (
    RevisionManifestResponse,
    RevisionManifestVerificationRequest,
    RevisionManifestVerificationResponse,
)
from app.schemas.review import EngineeringReviewResponse
from app.services.analysis_job_service import AnalysisJobService
from app.services.analysis_service import AnalysisService
from app.services.evidence_service import EvidenceSourceService
from app.analysis.manifest import RevisionManifestService

# Every analysis route requires auth; records are owner-scoped in the services.
router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])

_REPOSITORY_ID = "11111111-1111-1111-1111-111111111111"
_JOB_ID = "22222222-2222-2222-2222-222222222222"
_COMMON_ERRORS = (401, 404, 429, 500)
_CANCEL_ERRORS = (401, 404, 409, 429, 500)
_REVIEW_ERRORS = (401, 404, 422, 429, 500)


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
        "Architecture model derived from the sealed repository-intelligence snapshot "
        "bound to the repository's current revision. A repository with no sealed "
        "snapshot yet returns 404, never a fallback graph (#217).",
        {
            "repositoryId": _REPOSITORY_ID,
            "repositoryName": "example-service",
            "architectureType": "Layered application",
            "detectedLayers": [],
            "nodes": [],
            "edges": [],
            "modules": [],
            "requestFlow": [],
            "relationshipSnapshotId": "snap_example",
            "diagnostics": [],
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
    "/{repository_id}/evidence",
    response_model=EvidenceSourceResponse,
    dependencies=[Depends(require_repository_owner)],
    responses=documented_responses(
        200,
        "Source text for one evidence citation, verified against the exact snapshot revision it was cited from.",
        {
            "schemaVersion": "evidence-source.v1",
            "repositoryId": _REPOSITORY_ID,
            "snapshotId": "snap_example",
            "factId": "src/routes.py::(anonymous:route#1)",
            "revisionKind": "upload",
            "revisionValue": "sha256:" + "0" * 64,
            "path": "src/routes.py",
            "startLine": 10,
            "endLine": 10,
            "status": "ready",
            "reason": None,
            "content": '@app.get("/me")\n',
            "truncated": False,
            "size": 16,
        },
        401,
        404,
        422,
        429,
        500,
    ),
)
def get_evidence_source(
    repository_id: str,
    snapshot_id: str = Query(..., alias="snapshotId"),
    fact_id: str = Query(..., alias="factId", min_length=1, max_length=1024),
    path: str = Query(...),
    start_line: int = Query(..., alias="startLine", ge=1),
    end_line: int = Query(..., alias="endLine", ge=1),
    service: EvidenceSourceService = Depends(get_evidence_source_service),
) -> EvidenceSourceResponse:
    return service.read(repository_id, snapshot_id, fact_id, path, start_line, end_line)


_MANIFEST_EXAMPLE = {
    "manifest": {
        "schemaVersion": "revision-manifest.v1",
        "repositoryId": _REPOSITORY_ID,
        "revisionKind": "upload",
        "revisionValue": "sha256:" + "0" * 64,
        "revisionRef": None,
        "snapshotId": "snap_example",
        "snapshotSchemaVersion": "ri.v1",
        "extractors": [
            {"name": "typescript-extractor", "version": "1.0.0"},
            {"name": "relationship-resolver", "version": "1.0.0"},
        ],
        "producerSetHash": "sha256:" + "1" * 64,
        "configHash": "sha256:" + "2" * 64,
        "canonicalGraphHash": "sha256:" + "3" * 64,
        "createdAt": "2026-07-25T00:00:00Z",
        "sealedAt": "2026-07-25T00:00:05Z",
    },
    "manifestDigest": "sha256:" + "4" * 64,
    "verificationMethod": "sha256-canonical-json",
    "verificationState": "verified",
    "verificationNote": (
        "This digest is a SHA-256 over the canonical JSON encoding of the manifest "
        "fields above. It is a content hash, not a digital signature."
    ),
}


@router.get(
    "/{repository_id}/revision-manifest",
    response_model=RevisionManifestResponse,
    dependencies=[Depends(require_repository_owner)],
    responses=documented_responses(
        200,
        "Verifiable identity of the sealed snapshot backing this repository's "
        "evidence: revision, snapshot, extractor versions and canonical digest. "
        "The digest is a canonical content hash, not a digital signature.",
        _MANIFEST_EXAMPLE,
        *_COMMON_ERRORS,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_revision_manifest(
    repository_id: str,
    service: RevisionManifestService = Depends(get_revision_manifest_service),
) -> RevisionManifestResponse:
    return service.read(repository_id)


@router.post(
    "/{repository_id}/revision-manifest/verify",
    response_model=RevisionManifestVerificationResponse,
    dependencies=[Depends(require_repository_owner)],
    responses=documented_responses(
        200,
        "Re-check a previously exported manifest against the stored snapshot. "
        "Reports a mismatch when the supplied digest does not match the supplied "
        "manifest, or when the manifest does not match stored facts.",
        {
            "verificationState": "verified",
            "verificationMethod": "sha256-canonical-json",
            "matchesStoredSnapshot": True,
            "mismatchedFields": [],
            "detail": "The manifest matches the sealed snapshot stored for this repository.",
        },
        401,
        404,
        422,
        429,
        500,
    ),
)
def verify_revision_manifest(
    repository_id: str,
    request: RevisionManifestVerificationRequest,
    service: RevisionManifestService = Depends(get_revision_manifest_service),
) -> RevisionManifestVerificationResponse:
    return service.verify(repository_id, request.manifest, request.manifest_digest)


@router.get(
    "/{repository_id}/dependencies",
    response_model=DependencyGraphResponse,
    responses=documented_responses(
        200,
        "Dependency inventory and resolved depends_on relationships from the selected sealed ri.v1 snapshot.",
        {
            "schemaVersion": "dependency-graph.v2",
            "repositoryId": _REPOSITORY_ID,
            "repositoryName": "example-service",
            "revisionKind": "upload",
            "revisionValue": "sha256:" + "0" * 64,
            "snapshotId": "snap_example",
            "snapshotSchemaVersion": "ri.v1",
            "canonicalGraphHash": "sha256:" + "1" * 64,
            "manifestDigest": "sha256:" + "2" * 64,
            "provenance": {
                "source": "ri.v1",
                "snapshotId": "snap_example",
                "snapshotSchemaVersion": "ri.v1",
                "canonicalGraphHash": "sha256:" + "1" * 64,
            },
            "generatedAt": "2026-07-17T00:00:00Z",
            "nodes": [
                {
                    "id": "dep:npm:react",
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
                }
            ],
            "edges": [{"id": "edge_example", "source": "repo:root", "target": "dep:npm:react", "type": "depends-on"}],
            "totalDependencies": 1,
            "manifestCount": 1,
            "diagnostics": [],
            "vulnerabilityAssessment": {"status": "not_computed"},
            "outdatedAssessment": {"status": "not_computed"},
        },
        *_REVIEW_ERRORS,
    ),
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
        "Deterministic evidence-backed findings for the selected sealed ri.v1 snapshot.",
        {
            "schemaVersion": "engineering-review.v2",
            "repositoryId": _REPOSITORY_ID,
            "repositoryName": "example-service",
            "revisionKind": "upload",
            "revisionValue": "sha256:" + "0" * 64,
            "snapshotId": "snap_example",
            "snapshotSchemaVersion": "ri.v1",
            "canonicalGraphHash": "sha256:" + "1" * 64,
            "manifestDigest": "sha256:" + "2" * 64,
            "provenance": {
                "source": "ri.v1",
                "snapshotId": "snap_example",
                "snapshotSchemaVersion": "ri.v1",
                "canonicalGraphHash": "sha256:" + "1" * 64,
            },
            "generatedAt": "2026-07-17T00:00:00Z",
            "assessmentStatus": "partially_assessed",
            "categories": [],
            "findings": [],
            "summary": {
                "message": (
                    "0 evidence-backed findings were identified in this revision. "
                    "Security vulnerability scanning was not performed."
                ),
                "findingsBySeverity": {
                    "info": 0,
                    "low": 0,
                    "medium": 0,
                    "high": 0,
                    "critical": 0,
                },
                "assessedCategories": 2,
                "partiallyAssessedCategories": 4,
                "notAssessedCategories": 0,
                "insufficientEvidenceCategories": 1,
                "evidenceBackedFindingCount": 0,
                "fileScopedFindingCount": 0,
                "omittedUnsupportedDiagnosticCount": 0,
                "vulnerabilityScanning": "not_assessed",
            },
        },
        *_REVIEW_ERRORS,
    ),
)
def get_review(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> EngineeringReviewResponse:
    return service.engineering_review(repository_id)


@router.get(
    "/{repository_id}/insights",
    response_model=RepositoryInsightsResponse,
    responses=documented_responses(
        200,
        "Defined repository metrics computed only from the selected sealed ri.v1 snapshot.",
        {
            "schemaVersion": "repository-insights.v1",
            "repositoryId": _REPOSITORY_ID,
            "repositoryName": "example-service",
            "revisionKind": "upload",
            "revisionValue": "sha256:" + "0" * 64,
            "snapshotId": "snap_example",
            "snapshotSchemaVersion": "ri.v1",
            "canonicalGraphHash": "sha256:" + "1" * 64,
            "manifestDigest": "sha256:" + "2" * 64,
            "provenance": {
                "source": "ri.v1",
                "snapshotId": "snap_example",
                "snapshotSchemaVersion": "ri.v1",
                "canonicalGraphHash": "sha256:" + "1" * 64,
            },
            "computedAt": "2026-07-17T00:00:00Z",
            "snapshotCreatedAt": "2026-07-17T00:00:00Z",
            "snapshotSealedAt": "2026-07-17T00:00:00Z",
            "extractorSet": [],
            "metrics": [],
            "relationshipsByPredicate": [],
            "diagnosticsBySeverity": [],
            "diagnosticsByCode": [],
            "languages": [],
            "changeOverTime": {
                "assessmentState": "not_assessed",
                "message": "Change-over-time insights are not available yet.",
            },
        },
        *_REVIEW_ERRORS,
    ),
)
def get_insights(
    repository_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> RepositoryInsightsResponse:
    return service.repository_insights(repository_id)
