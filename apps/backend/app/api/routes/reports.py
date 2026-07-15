from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_export_service
from app.reports.export_service import ExportService
from app.schemas.reports import ExportRequest, ExportResponse

# The export route requires auth; the underlying analysis/documentation services
# resolve the repository owner-scoped, so exports return only the caller's data.
router = APIRouter(tags=["export"], dependencies=[Depends(get_current_user)])


@router.post("/export", response_model=ExportResponse)
def export_report(
    request: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> ExportResponse:
    return service.export(request)
