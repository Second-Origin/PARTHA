from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Response, UploadFile, status

from app.api.deps import get_current_user, get_repository_service
from app.api.openapi import documented_responses, error_responses, suppress_automatic_validation_error
from app.schemas.repository import (
    GitHubImportRequest,
    RepositoryFileResponse,
    RepositoryLineageResponse,
    RepositoryListResponse,
    RepositoryResponse,
)
from app.services.repository_service import RepositoryService

# Router-level auth: every repository route requires a valid access token, so a
# new route added here is protected by default instead of by remembering to add
# a dependency. Data is additionally owner-scoped inside RepositoryService.
router = APIRouter(prefix="/repositories", tags=["repositories"], dependencies=[Depends(get_current_user)])

_REPOSITORY_ID = "11111111-1111-1111-1111-111111111111"
_REPOSITORY_EXAMPLE = {
    "id": _REPOSITORY_ID,
    "name": "example-service",
    "description": None,
    "source": "github",
    "sourceUrl": "https://github.com/example/example-service",
    "branch": "main",
    "size": 2048,
    "fileCount": 12,
    "status": "completed",
    "analysisStage": "completed",
    "analysisProgress": 100,
    "uploadedAt": "2026-07-17T00:00:00Z",
    "analysedAt": "2026-07-17T00:00:02Z",
    "errorMessage": None,
    "revision": {
        "kind": "git",
        "value": "0123456789abcdef0123456789abcdef01234567",
        "ref": "refs/heads/main",
    },
    "commitSha": "0123456789abcdef0123456789abcdef01234567",
    "meta": None,
    "fileTree": [],
}
_REPOSITORY_LINEAGE_EXAMPLE = {
    "isLineaged": True,
    "lineageId": "22222222-2222-2222-2222-222222222222",
    "canonicalSourceKey": "github.com/example/example-service",
    "canonicalBranch": "refs/heads/main",
    "entries": [
        {
            "repositoryId": _REPOSITORY_ID,
            "sequence": 2,
            "name": "example-service",
            "status": "completed",
            "revision": {
                "kind": "git",
                "value": "0123456789abcdef0123456789abcdef01234567",
                "ref": "refs/heads/main",
            },
            "uploadedAt": "2026-07-17T00:00:00Z",
            "isCurrent": True,
        },
        {
            "repositoryId": "33333333-3333-3333-3333-333333333333",
            "sequence": 1,
            "name": "example-service",
            "status": "completed",
            "revision": {
                "kind": "git",
                "value": "abcdef0123456789abcdef0123456789abcdef01",
                "ref": "refs/heads/main",
            },
            "uploadedAt": "2026-06-01T00:00:00Z",
            "isCurrent": False,
        },
    ],
}
_GITHUB_IMPORT_EXAMPLE = {
    "summary": "Import a public GitHub repository",
    "value": {"url": "https://github.com/octocat/Hello-World", "branch": "master"},
}


@router.post(
    "/upload",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=documented_responses(
        status.HTTP_201_CREATED,
        "Repository archive accepted and parsed.",
        _REPOSITORY_EXAMPLE,
        401,
        409,
        422,
        429,
        500,
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "examples": {
                        "archive": {
                            "summary": "Repository archive",
                            "value": {"file": "example-service.zip"},
                        }
                    }
                }
            }
        }
    },
)
async def upload_repository(
    file: UploadFile,
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    return await service.import_uploaded_repository(file)


@router.post(
    "/github",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=documented_responses(
        status.HTTP_201_CREATED,
        "Public GitHub repository cloned and parsed.",
        _REPOSITORY_EXAMPLE,
        401,
        409,
        422,
        429,
        502,
        504,
        500,
    ),
)
def import_github_repository(
    request: Annotated[GitHubImportRequest, Body(openapi_examples={"github": _GITHUB_IMPORT_EXAMPLE})],
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    return service.import_github_repository(request)


@router.get(
    "",
    response_model=RepositoryListResponse,
    responses=documented_responses(
        status.HTTP_200_OK,
        "Repositories owned by the authenticated user.",
        {"data": [_REPOSITORY_EXAMPLE], "total": 1},
        401,
        429,
        500,
    ),
)
def list_repositories(
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryListResponse:
    return service.list_repositories()


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    responses=documented_responses(
        status.HTTP_200_OK,
        "Repository metadata and file tree.",
        _REPOSITORY_EXAMPLE,
        401,
        404,
        429,
        500,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_repository(
    repository_id: str,
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    return service.get_repository(repository_id)


@router.get(
    "/{repository_id}/lineage",
    response_model=RepositoryLineageResponse,
    responses=documented_responses(
        status.HTTP_200_OK,
        "History of repository imports this repository belongs to, most recent first. "
        "A standalone (unlineaged) repository returns `isLineaged: false` and a single entry: itself.",
        _REPOSITORY_LINEAGE_EXAMPLE,
        401,
        404,
        429,
        500,
    ),
    openapi_extra=suppress_automatic_validation_error(),
)
def get_repository_lineage(
    repository_id: str,
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryLineageResponse:
    return service.get_lineage(repository_id)


@router.get(
    "/{repository_id}/file",
    response_model=RepositoryFileResponse,
    responses=documented_responses(
        status.HTTP_200_OK,
        "Preview of a repository-relative file.",
        {
            "path": "/README.md",
            "content": "# Example service\\n",
            "size": 18,
            "truncated": False,
            "isBinary": False,
            "isImage": False,
            "mediaType": None,
        },
        401,
        404,
        422,
        429,
        500,
    ),
)
def get_repository_file(
    repository_id: str,
    path: str = Query(..., description="Repository-relative file path."),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryFileResponse:
    return service.read_file(repository_id, path)


@router.delete(
    "/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404, 429, 500),
    openapi_extra=suppress_automatic_validation_error(),
)
def delete_repository(
    repository_id: str,
    service: RepositoryService = Depends(get_repository_service),
) -> Response:
    service.delete_repository(repository_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
