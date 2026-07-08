from typing import Literal

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


class ArchEdge(CamelModel):
    id: str
    source: str
    target: str
    label: str | None = None
    type: ArchEdgeType


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
