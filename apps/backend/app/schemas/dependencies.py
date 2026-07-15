from typing import Literal

from app.schemas.base import CamelModel


class DependencyNode(CamelModel):
    id: str
    name: str
    version: str
    type: Literal["production", "development", "peer", "optional"]
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
    vulnerability_assessment: DependencyAssessment
    outdated_assessment: DependencyAssessment
