from app.intelligence.engine import RepositoryIntelligenceEngine
from app.intelligence.models import RepositoryModule
from app.models.repository import RepositoryRecord
from app.schemas.architecture import (
    ArchEdge,
    ArchLayer,
    ArchModule,
    ArchitectureResponse,
    ArchitectureSummary,
    ArchNode,
    RequestFlowStep,
)


ROLE_TO_NODE_TYPE = {
    "entrypoint": "frontend",
    "controller": "controller",
    "route": "route",
    "service": "service",
    "repository": "repository",
    "model": "models",
    "dto": "models",
    "interface": "models",
    "enum": "models",
    "utility": "utilities",
    "configuration": "configuration",
    "test": "utilities",
    "documentation": "shared-library",
    "unknown": "shared-library",
}


class ArchitectureAnalyzer:
    def __init__(self, intelligence: RepositoryIntelligenceEngine | None = None) -> None:
        self.intelligence = intelligence or RepositoryIntelligenceEngine()

    def build_architecture(self, record: RepositoryRecord) -> ArchitectureResponse:
        repository_intelligence = self.intelligence.from_record(record)
        modules = repository_intelligence.modules or [
            RepositoryModule(
                id="module:repository",
                name="Repository",
                role="unknown",
                layer="shared",
                path_prefix="/",
                files=[file.path for file in repository_intelligence.files[:25]],
                symbols=[],
                dependencies=[],
            )
        ]
        nodes = self._nodes_for_modules(modules)
        edges = self._edges_for_modules(modules, nodes)
        layers = self._layers_for_nodes(nodes)
        arch_modules = [
            ArchModule(
                id=module.id,
                name=module.name,
                layer=module.layer,
                node_ids=[module.id],
                description=f"{module.name} module derived from repository intelligence.",
                file_count=len(module.files),
            )
            for module in modules
        ]
        return ArchitectureResponse(
            repository_id=record.id,
            repository_name=record.name,
            architecture_type=self._architecture_type(repository_intelligence.discovery.frameworks),
            detected_layers=layers,
            nodes=nodes,
            edges=edges,
            modules=arch_modules,
            request_flow=self._request_flow(modules),
            summary=ArchitectureSummary(
                language=repository_intelligence.discovery.primary_language,
                framework=repository_intelligence.discovery.frameworks[0] if repository_intelligence.discovery.frameworks else "Unknown",
                total_modules=len(arch_modules),
                total_nodes=len(nodes),
                entry_point=repository_intelligence.discovery.entry_points[0] if repository_intelligence.discovery.entry_points else "/",
                architecture_pattern=self._architecture_type(repository_intelligence.discovery.frameworks),
            ),
        )

    def _nodes_for_modules(self, modules: list[RepositoryModule]) -> list[ArchNode]:
        nodes: list[ArchNode] = []
        for module in modules:
            node_type = ROLE_TO_NODE_TYPE.get(module.role, "shared-library")
            nodes.append(
                ArchNode(
                    id=module.id,
                    name=module.name,
                    type=node_type,  # type: ignore[arg-type]
                    description=f"{module.name} derived from repository intelligence at {module.path_prefix}.",
                    responsibilities=[f"Owns {module.role} concerns"],
                    files=module.files[:25],
                    dependencies=[],
                    dependents=[],
                    estimated_complexity="high" if len(module.files) > 30 else "medium" if len(module.files) > 10 else "low",
                    estimated_lines=max(len(module.files) * 80, 20),
                    tags=[module.layer, module.role, module.id.replace("module:", "")],
                    layer=module.layer,
                )
            )
        return nodes

    def _edges_for_modules(self, modules: list[RepositoryModule], nodes: list[ArchNode]) -> list[ArchEdge]:
        node_ids = {node.id for node in nodes}
        module_by_role = {module.role: module.id for module in modules}
        candidates = [
            ("entrypoint", "route"),
            ("entrypoint", "controller"),
            ("route", "service"),
            ("controller", "service"),
            ("service", "repository"),
            ("service", "model"),
            ("repository", "model"),
            ("test", "service"),
        ]
        edges: list[ArchEdge] = []
        for source_role, target_role in candidates:
            source = module_by_role.get(source_role)
            target = module_by_role.get(target_role)
            if source in node_ids and target in node_ids and source != target:
                edges.append(ArchEdge(id=f"{source}->{target}", source=source, target=target, type="dependency", label="uses"))
        for edge in edges:
            source = next(node for node in nodes if node.id == edge.source)
            target = next(node for node in nodes if node.id == edge.target)
            source.dependencies.append(target.id)
            target.dependents.append(source.id)
        return edges

    def _layers_for_nodes(self, nodes: list[ArchNode]) -> list[ArchLayer]:
        order = {"presentation": 0, "business-logic": 1, "domain": 2, "infrastructure": 3, "shared": 4}
        layers: dict[str, list[str]] = {}
        for node in nodes:
            layers.setdefault(node.layer, []).append(node.id)
        return [
            ArchLayer(id=layer, name=layer.replace("-", " ").title(), order=order.get(layer, 99), nodes=node_ids)
            for layer, node_ids in sorted(layers.items(), key=lambda item: order.get(item[0], 99))
        ]

    def _architecture_type(self, frameworks: list[str]) -> str:
        if any(framework in {"React", "Next.js", "Vue"} for framework in frameworks):
            return "Client Application"
        if any(framework in {"FastAPI", "Django", "Flask"} for framework in frameworks):
            return "Backend Service"
        return "Repository Architecture"

    def _request_flow(self, modules: list[RepositoryModule]) -> list[RequestFlowStep]:
        module_roles = {module.role for module in modules}
        steps = [
            RequestFlowStep(id="client", name="Client", type="frontend", description="Request enters the system.", details=["Browser or API client sends a request."]),
        ]
        if "route" in module_roles or "controller" in module_roles:
            steps.append(RequestFlowStep(id="api", name="API Layer", type="controller", description="Route/controller handles input.", details=["Validate request", "Call service"]))
        if "service" in module_roles:
            steps.append(RequestFlowStep(id="service", name="Service Layer", type="service", description="Business logic executes.", details=["Coordinate repository intelligence consumers", "Transform data"]))
        if "repository" in module_roles:
            steps.append(RequestFlowStep(id="repository", name="Repository Layer", type="repository", description="Persistence or source files are accessed.", details=["Read or write data"] ))
        return steps
