from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel

ReviewSeverity = Literal["critical", "high", "medium", "low"]
ReviewStatus = Literal["open", "acknowledged", "resolved"]
ReviewCategory = Literal[
    "architecture",
    "security",
    "performance",
    "maintainability",
    "scalability",
    "code-quality",
    "documentation",
    "testing",
    "dependency-health",
    "configuration",
]


class ReviewFileEvidence(CamelModel):
    path: str
    size_bytes: int


class ReviewFinding(CamelModel):
    id: str
    title: str
    category: ReviewCategory
    severity: ReviewSeverity
    status: ReviewStatus
    problem: str
    impact: str
    recommendation: str
    priority: int
    estimated_effort: Literal["trivial", "small", "medium", "large", "major"]
    affected_files: list[str]
    affected_file_details: list[ReviewFileEvidence] = Field(default_factory=list)
    affected_modules: list[str]
    tags: list[str]


class ReviewScore(CamelModel):
    category: ReviewCategory
    score: int
    trend: Literal["improving", "stable", "declining"]
    risk_level: ReviewSeverity
    priority: int
    findings_count: int


class ReviewSummary(CamelModel):
    overall_score: int
    overall_trend: Literal["improving", "stable", "declining"]
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    total_findings: int


class ImprovementStep(CamelModel):
    id: str
    title: str
    description: str
    priority: ReviewSeverity
    estimated_effort: str
    category: ReviewCategory
    related_findings: list[str]


class EngineeringReviewResponse(CamelModel):
    repository_id: str
    repository_name: str
    generated_at: datetime
    summary: ReviewSummary
    scores: list[ReviewScore]
    findings: list[ReviewFinding]
    roadmap: list[ImprovementStep]
