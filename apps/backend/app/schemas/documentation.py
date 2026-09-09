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
    source: Literal["ri.v1"]
    snapshot_id: str
    snapshot_schema_version: Literal["ri.v1"]
    revision_kind: Literal["git", "upload"]
    revision_value: str
    revision_ref: str | None = None
