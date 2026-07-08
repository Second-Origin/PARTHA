from typing import Literal

from app.schemas.base import CamelModel


class DependencyNode(CamelModel):
    id: str
    name: str
    version: str
    type: Literal["production", "development", "peer", "optional"]
    has_vulnerabilities: bool
    is_outdated: bool
    size: int | None = None


class DependencyEdge(CamelModel):
    source: str
    target: str
    type: Literal["depends-on", "peer", "optional"]


class DependencyGraphResponse(CamelModel):
    repository_id: str
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    total_dependencies: int
    vulnerabilities: int
    outdated: int
