from typing import Literal

from app.schemas.base import CamelModel
from app.schemas.provenance import IntelligenceProvenance


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
    size: int | None = None


class DependencyEdge(CamelModel):
    source: str
    target: str
    type: Literal["depends-on", "peer", "optional"]


class DependencyAssessment(CamelModel):
    status: Literal["not_computed"]


class DependencyGraphResponse(CamelModel):
    repository_id: str
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    total_dependencies: int
    manifest_count: int = 0
    diagnostics: list[DependencyDiagnostic] = []
    vulnerability_assessment: DependencyAssessment
    outdated_assessment: DependencyAssessment
    #: The dependency graph is still built by the legacy engine, so every
    #: response declares that provenance rather than letting the surface imply
    #: it is snapshot-backed.
    provenance: IntelligenceProvenance
