from typing import Literal

from app.schemas.base import CamelModel

ExportTarget = Literal["review", "documentation", "architecture", "dependencies"]
ExportFormat = Literal["json", "markdown", "html", "pdf"]


class ExportRequest(CamelModel):
    repository_id: str
    target: ExportTarget
    format: ExportFormat


class ExportResponse(CamelModel):
    filename: str
    media_type: str
    encoding: Literal["utf-8", "base64"]
    content: str
