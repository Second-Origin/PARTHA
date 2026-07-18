from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel

ArchNodeType = Literal[
    "frontend",
    "backend",
    "controller",
    "route",
    "service",
    "repository",
    "database",
    "configuration",
    "authentication",
    "middleware",
    "utilities",
    "models",
    "external-api",
    "shared-library",
    "environment",
    "queue",
    "cache",
]
ArchEdgeType = Literal["dependency", "import", "api-call", "data-flow", "event", "reads", "writes", "calls", "config-usage"]
RelationshipState = Literal["connected", "no-observed-relationships", "unresolved", "not-extracted"]
TruthClass = Literal["resolved", "inferred"]


class ArchEvidence(CamelModel):
    snapshot_id: str
    fact_id: str
    path: str
    start_line: int
    end_line: int


class ArchitectureDiagnostic(CamelModel):
    code: str
    category: str
    severity: Literal["fatal", "error", "warning", "info"]
    message: str
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    subject_key: str | None = None
    object_key: str | None = None
    details: dict[str, object] | None = None
    node_ids: list[str] | None = None


class ArchNode(CamelModel):
    id: str
    name: str
    type: ArchNodeType
    description: str
    responsibilities: list[str]
    files: list[str]
    dependencies: list[str]
    dependents: list[str]
    estimated_complexity: Literal["low", "medium", "high"]
    estimated_lines: int
    tags: list[str]
    layer: str
    parent_module: str | None = None
    relationship_state: RelationshipState = "not-extracted"


class ArchEdge(CamelModel):
    id: str
    source: str
    target: str
    label: str | None = None
    type: ArchEdgeType
    predicate: str
    truth_class: TruthClass
    evidence: list[ArchEvidence]


class ArchLayer(CamelModel):
    id: str
    name: str
    order: int
    nodes: list[str]


class ArchModule(CamelModel):
    id: str
    name: str
    layer: str
    node_ids: list[str]
    description: str
    file_count: int


class RequestFlowStep(CamelModel):
    id: str
    name: str
    type: ArchNodeType
    description: str
    details: list[str]


class ArchitectureSummary(CamelModel):
    language: str
    framework: str
    total_modules: int
    total_nodes: int
    entry_point: str
    architecture_pattern: str


class ArchitectureResponse(CamelModel):
    repository_id: str
    repository_name: str
    architecture_type: str
    detected_layers: list[ArchLayer]
    nodes: list[ArchNode]
    edges: list[ArchEdge]
    modules: list[ArchModule]
    request_flow: list[RequestFlowStep]
    summary: ArchitectureSummary
    relationship_snapshot_id: str | None = None
    diagnostics: list[ArchitectureDiagnostic] = Field(default_factory=list)
