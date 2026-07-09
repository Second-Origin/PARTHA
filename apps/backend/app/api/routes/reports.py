from fastapi import APIRouter, Depends

from app.api.deps import get_export_service
from app.reports.export_service import ExportService
from app.schemas.reports import ExportRequest, ExportResponse

router = APIRouter(tags=["export"])


@router.post("/export", response_model=ExportResponse)
def export_report(
    request: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> ExportResponse:
    return service.export(request)
