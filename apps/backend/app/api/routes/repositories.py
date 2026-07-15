from fastapi import APIRouter, Depends, Query, Response, UploadFile, status

from app.api.deps import get_current_user, get_repository_service
from app.schemas.repository import (
    GitHubImportRequest,
    RepositoryFileResponse,
    RepositoryListResponse,
    RepositoryResponse,
)
from app.services.repository_service import RepositoryService

# Router-level auth: every repository route requires a valid access token, so a
# new route added here is protected by default instead of by remembering to add
# a dependency. Data is additionally owner-scoped inside RepositoryService.
router = APIRouter(prefix="/repositories", tags=["repositories"], dependencies=[Depends(get_current_user)])


@router.post("/upload", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def upload_repository(
    file: UploadFile,
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    return await service.import_uploaded_repository(file)


@router.post("/github", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def import_github_repository(
    request: GitHubImportRequest,
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    return service.import_github_repository(request)


@router.get("", response_model=RepositoryListResponse)
def list_repositories(
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryListResponse:
    return service.list_repositories()


@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository(
    repository_id: str,
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    return service.get_repository(repository_id)


@router.get("/{repository_id}/file", response_model=RepositoryFileResponse)
def get_repository_file(
    repository_id: str,
    path: str = Query(..., description="Repository-relative file path."),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryFileResponse:
    return service.read_file(repository_id, path)


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repository_id: str,
    service: RepositoryService = Depends(get_repository_service),
) -> Response:
    service.delete_repository(repository_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
