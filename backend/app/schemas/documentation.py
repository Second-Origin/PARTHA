from datetime import datetime
from typing import Literal

from app.schemas.base import CamelModel


class GenerateDocRequest(CamelModel):
    repository_id: str
    format: Literal["markdown", "html"] = "markdown"
    sections: list[str] | None = None


class GenerateDocResponse(CamelModel):
    content: str
    format: Literal["markdown", "html"]
    generated_at: datetime


class ExportRequest(CamelModel):
    repository_id: str
    format: Literal["png", "svg", "json", "markdown", "pdf"]
    target: Literal["architecture", "review", "dependencies", "documentation"]


class ExportResponse(CamelModel):
    url: str
    expires_at: datetime
