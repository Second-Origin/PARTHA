from datetime import datetime
from typing import Literal

from app.schemas.base import CamelModel
from app.schemas.repository import AnalysisStage


class AnalysisStartResponse(CamelModel):
    repository_id: str
    status: Literal["queued", "processing", "completed", "failed"]


class AnalysisStatusResponse(CamelModel):
    repository_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    stage: AnalysisStage | None = None
    progress: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
