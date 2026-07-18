from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.schemas.dependencies import (
    DependencyAssessment,
    DependencyEdge,
    DependencyGraphResponse,
    DependencyNode,
)


class DependencyGraphBuilder:
    def __init__(self, intelligence: RepositoryIntelligenceEngine | None = None) -> None:
        self.intelligence = intelligence or RepositoryIntelligenceEngine()

    def build(self, record: RepositoryRecord) -> DependencyGraphResponse:
        repository_intelligence = self.intelligence.from_record(record)
        nodes = [
            DependencyNode(
                id=dependency.id,
                name=dependency.name,
                version=dependency.version,
                type=dependency.type,
                ecosystem=dependency.ecosystem,
                declarations=dependency.declarations,
                size=None,
            )
            for dependency in repository_intelligence.dependencies
        ]
        dependency_ids = {dependency.id for dependency in repository_intelligence.dependencies}
        edges = [
            DependencyEdge(source=relationship.source, target=relationship.target, type="depends-on")
            for relationship in repository_intelligence.graph.relationships
            if relationship.type == "depends_on" and relationship.target in dependency_ids
        ]
        return DependencyGraphResponse(
            repository_id=record.id,
            nodes=nodes,
            edges=edges,
            total_dependencies=len(nodes),
            manifest_count=repository_intelligence.dependency_manifest_count,
            diagnostics=repository_intelligence.dependency_diagnostics,
            vulnerability_assessment=DependencyAssessment(status="not_computed"),
            outdated_assessment=DependencyAssessment(status="not_computed"),
        )
