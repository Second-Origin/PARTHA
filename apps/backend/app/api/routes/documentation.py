from fastapi import APIRouter, Depends

from app.api.deps import get_documentation_service
from app.schemas.documentation import GenerateDocRequest, GenerateDocResponse
from app.services.documentation_service import DocumentationService

router = APIRouter(prefix="/documentation", tags=["documentation"])


@router.post("/generate", response_model=GenerateDocResponse)
def generate_documentation(
    request: GenerateDocRequest,
    service: DocumentationService = Depends(get_documentation_service),
) -> GenerateDocResponse:
    return service.generate(request)
