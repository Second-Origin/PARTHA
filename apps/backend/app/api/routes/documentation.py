from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.api.deps import get_current_user, get_documentation_service
from app.api.openapi import documented_responses
from app.schemas.documentation import GenerateDocRequest, GenerateDocResponse
from app.services.documentation_service import DocumentationService

# Every documentation route requires auth; records are owner-scoped in the service.
router = APIRouter(prefix="/documentation", tags=["documentation"], dependencies=[Depends(get_current_user)])

_REQUEST_EXAMPLE = {
    "summary": "Generate a concise Markdown document",
    "value": {
        "repositoryId": "11111111-1111-1111-1111-111111111111",
        "format": "markdown",
        "sections": ["overview", "architecture"],
    },
}
_RESPONSE_EXAMPLE = {
    "content": "# Example service\\n\\n## Overview\\n\\nGenerated documentation.",
    "format": "markdown",
    "generatedAt": "2026-07-17T00:00:00Z",
    "source": "ri.v1",
    "snapshotId": "snap_example",
    "snapshotSchemaVersion": "ri.v1",
    "revisionKind": "git",
    "revisionValue": "0123456789abcdef0123456789abcdef01234567",
    "revisionRef": "refs/heads/main",
}


@router.post(
    "/generate",
    response_model=GenerateDocResponse,
    responses=documented_responses(
        200,
        "Generated documentation for the requested repository.",
        _RESPONSE_EXAMPLE,
        401,
        404,
        422,
        429,
        500,
    ),
)
def generate_documentation(
    request: Annotated[GenerateDocRequest, Body(openapi_examples={"markdown": _REQUEST_EXAMPLE})],
    service: DocumentationService = Depends(get_documentation_service),
) -> GenerateDocResponse:
    return service.generate(request)
