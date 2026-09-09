from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.api.deps import get_current_user, get_export_service
from app.api.openapi import documented_responses
from app.reports.export_service import ExportService
from app.schemas.reports import ExportRequest, ExportResponse

# The export route requires auth; the underlying analysis/documentation services
# resolve the repository owner-scoped, so exports return only the caller's data.
router = APIRouter(tags=["export"], dependencies=[Depends(get_current_user)])

_REQUEST_EXAMPLE = {
    "summary": "Export the engineering review as JSON",
    "value": {
        "repositoryId": "11111111-1111-1111-1111-111111111111",
        "target": "review",
        "format": "json",
    },
}
_RESPONSE_EXAMPLE = {
    "filename": "engineering-review.json",
    "mediaType": "application/json",
    "encoding": "utf-8",
    "content": '{\\n  \\"repositoryId\\": \\"11111111-1111-1111-1111-111111111111\\"\\n}',
}


@router.post(
    "/export",
    response_model=ExportResponse,
    responses=documented_responses(
        200,
        "Repository report rendered in the requested format; an uncomputed review returns 409.",
        _RESPONSE_EXAMPLE,
        401,
        404,
        409,
        422,
        429,
        500,
    ),
)
def export_report(
    request: Annotated[ExportRequest, Body(openapi_examples={"review-json": _REQUEST_EXAMPLE})],
    service: ExportService = Depends(get_export_service),
) -> ExportResponse:
    return service.export(request)
