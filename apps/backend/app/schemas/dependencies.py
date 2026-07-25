"""Snapshot-bound Dependency Graph public contract (#158).

This replaces the legacy-heuristic response: every field is built from sealed
``ri.v1`` facts (``app/graph/dependency_graph.py``), never from the mutable
``repo_metadata['intelligence']`` blob.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel

DependencySchemaVersion = Literal["dependency-graph.v2"]


class DependencyProvenance(CamelModel):
    source: Literal["ri.v1"] = "ri.v1"
    snapshot_id: str
    snapshot_schema_version: str
    canonical_graph_hash: str


class DependencyDeclaration(CamelModel):
    name: str
    manifest_path: str
    workspace_path: str
    start_line: int
    end_line: int
    extractor: str
    extractor_version: str
    ecosystem: str
    version: str | None
    type: Literal["production", "development", "peer", "optional"]


class DependencyDiagnostic(CamelModel):
    code: str
    category: str
    severity: Literal["fatal", "error", "warning", "info"]
    message: str
    path: str | None = None
    producer: str
    details: dict[str, object] | None = None


class DependencyNode(CamelModel):
    id: str
    name: str
    version: str | None
    type: Literal["production", "development", "peer", "optional", "multiple"]
    ecosystem: str
    declarations: list[DependencyDeclaration]


class DependencyEdge(CamelModel):
    id: str
    source: str
    target: str
    type: Literal["depends-on"]


class DependencyAssessment(CamelModel):
    status: Literal["not_computed"]


class DependencyGraphResponse(CamelModel):
    schema_version: DependencySchemaVersion = "dependency-graph.v2"
    repository_id: str
    repository_name: str
    revision_kind: Literal["git", "upload"]
    revision_value: str
    snapshot_id: str
    snapshot_schema_version: str
    canonical_graph_hash: str
    manifest_digest: str
    provenance: DependencyProvenance
    generated_at: datetime
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    total_dependencies: int
    manifest_count: int = 0
    diagnostics: list[DependencyDiagnostic] = Field(default_factory=list)
    vulnerability_assessment: DependencyAssessment
    outdated_assessment: DependencyAssessment
