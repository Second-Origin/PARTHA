from fastapi import APIRouter, Depends, Response, UploadFile, status

from app.api.deps import get_repository_service
from app.schemas.repository import GitHubImportRequest, RepositoryListResponse, RepositoryResponse
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["repositories"])


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


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repository_id: str,
    service: RepositoryService = Depends(get_repository_service),
) -> Response:
    service.delete_repository(repository_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
