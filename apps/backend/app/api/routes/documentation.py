from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_documentation_service
from app.schemas.documentation import GenerateDocRequest, GenerateDocResponse
from app.services.documentation_service import DocumentationService

# Every documentation route requires auth; records are owner-scoped in the service.
router = APIRouter(prefix="/documentation", tags=["documentation"], dependencies=[Depends(get_current_user)])


@router.post("/generate", response_model=GenerateDocResponse)
def generate_documentation(
    request: GenerateDocRequest,
    service: DocumentationService = Depends(get_documentation_service),
) -> GenerateDocResponse:
    return service.generate(request)
