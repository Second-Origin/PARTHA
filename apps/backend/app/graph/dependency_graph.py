from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.schemas.dependencies import DependencyEdge, DependencyGraphResponse, DependencyNode


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
                has_vulnerabilities=False,
                is_outdated=False,
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
            vulnerabilities=0,
            outdated=0,
        )
