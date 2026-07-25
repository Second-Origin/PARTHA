"""Evidence-backed Engineering Review public contract (#154).

This intentionally replaces the legacy score/grade/roadmap response.  A review
finding is a deterministic view over a sealed ``ri.v1`` diagnostic and an
exact, same-snapshot evidence span.  Diagnostics without support are omitted
rather than promoted into repository claims.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel

ReviewSchemaVersion = Literal["engineering-review.v2"]
ReviewSeverity = Literal["info", "low", "medium", "high", "critical"]
AssessmentState = Literal[
    "assessed",
    "partially_assessed",
    "not_assessed",
    "insufficient_evidence",
]
ReviewCategoryId = Literal[
    "architecture_boundaries",
    "relationship_resolution",
    "source_extraction",
    "dependency_declarations",
    "security_vulnerability_scanning",
    "authentication_evidence",
    "repository_structure",
    "analysis_integrity",
]


class ReviewProvenance(CamelModel):
    source: Literal["ri.v1"] = "ri.v1"
    snapshot_id: str
    snapshot_schema_version: str
    canonical_graph_hash: str


class ReviewEvidenceReference(CamelModel):
    evidence_id: str
    snapshot_id: str
    fact_id: str
    path: str
    start_line: int
    end_line: int
    extractor_name: str
    extractor_version: str


class ReviewFinding(CamelModel):
    id: str
    category: ReviewCategoryId
    severity: ReviewSeverity
    title: str
    explanation: str
    path: str
    start_line: int
    end_line: int
    snapshot_id: str
    fact_id: str
    evidence_id: str
    extractor_name: str
    extractor_version: str
    diagnostic_code: str
    rule_id: str
    remediation_guidance: str
    support_status: Literal["supported"] = "supported"
    provenance: ReviewProvenance
    evidence: ReviewEvidenceReference


class ReviewCategoryAssessment(CamelModel):
    id: ReviewCategoryId
    label: str
    state: AssessmentState
    explanation: str
    finding_count: int = 0


class ReviewSeverityCounts(CamelModel):
    info: int = 0
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


class ReviewSummary(CamelModel):
    message: str
    findings_by_severity: ReviewSeverityCounts
    assessed_categories: int
    partially_assessed_categories: int
    not_assessed_categories: int
    insufficient_evidence_categories: int
    evidence_backed_finding_count: int
    unsupported_finding_count: int = 0
    omitted_unsupported_diagnostic_count: int = 0
    vulnerability_scanning: Literal["not_assessed"] = "not_assessed"


class EngineeringReviewResponse(CamelModel):
    schema_version: ReviewSchemaVersion = "engineering-review.v2"
    repository_id: str
    repository_name: str
    revision_kind: Literal["git", "upload"]
    revision_value: str
    snapshot_id: str
    snapshot_schema_version: str
    canonical_graph_hash: str
    manifest_digest: str
    provenance: ReviewProvenance
    generated_at: datetime
    assessment_status: AssessmentState
    categories: list[ReviewCategoryAssessment] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: ReviewSummary
