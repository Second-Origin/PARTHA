from datetime import datetime
from typing import Literal

from app.schemas.base import CamelModel
from app.schemas.repository import AnalysisStage

# The five explicit lifecycle states from #93 ("No implicit states"). The legacy
# ``processing`` value was renamed to ``running`` and ``cancelled`` was added; the
# frontend is updated to match in Task 5.
AnalysisJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class AnalysisStartResponse(CamelModel):
    repository_id: str
    status: AnalysisJobStatus
    job_id: str | None = None


class AnalysisStatusResponse(CamelModel):
    repository_id: str
    status: AnalysisJobStatus
    job_id: str | None = None
    stage: AnalysisStage | None = None
    progress: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
