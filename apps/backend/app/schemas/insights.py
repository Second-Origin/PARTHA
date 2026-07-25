"""Snapshot-backed repository Insights contract (#154)."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel

InsightsSchemaVersion = Literal["repository-insights.v1"]
MetricAssessmentState = Literal["assessed", "not_assessed", "insufficient_evidence"]


class InsightProvenance(CamelModel):
    source: Literal["ri.v1"] = "ri.v1"
    snapshot_id: str
    snapshot_schema_version: str
    canonical_graph_hash: str


class InsightExtractor(CamelModel):
    name: str
    version: str
    evidence_record_count: int


class InsightMetric(CamelModel):
    id: str
    label: str
    value: int | float | str | None
    unit: str
    definition: str
    provenance: InsightProvenance
    assessment_state: MetricAssessmentState
    snapshot_id: str
    numerator: int | None = None
    denominator: int | None = None


class InsightBreakdown(CamelModel):
    key: str
    label: str
    value: int


class ChangeOverTimeAssessment(CamelModel):
    assessment_state: Literal["not_assessed"] = "not_assessed"
    message: str = "Change-over-time insights are not available yet."


class RepositoryInsightsResponse(CamelModel):
    schema_version: InsightsSchemaVersion = "repository-insights.v1"
    repository_id: str
    repository_name: str
    revision_kind: Literal["git", "upload"]
    revision_value: str
    snapshot_id: str
    snapshot_schema_version: str
    canonical_graph_hash: str
    manifest_digest: str
    provenance: InsightProvenance
    computed_at: datetime
    snapshot_created_at: datetime
    snapshot_sealed_at: datetime
    extractor_set: list[InsightExtractor] = Field(default_factory=list)
    metrics: list[InsightMetric] = Field(default_factory=list)
    relationships_by_predicate: list[InsightBreakdown] = Field(default_factory=list)
    diagnostics_by_severity: list[InsightBreakdown] = Field(default_factory=list)
    diagnostics_by_code: list[InsightBreakdown] = Field(default_factory=list)
    languages: list[InsightBreakdown] = Field(default_factory=list)
    change_over_time: ChangeOverTimeAssessment = Field(default_factory=ChangeOverTimeAssessment)
