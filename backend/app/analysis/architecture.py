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


class ArchitectureAnalyzer:
    def build_architecture(self, record: RepositoryRecord) -> ArchitectureResponse:
        meta = record.repo_metadata or {}
        paths = self._file_paths(record)
        nodes = self._nodes_for_paths(paths)
        edges = self._edges_for_nodes(nodes)
        layers = self._layers_for_nodes(nodes)
        modules = [
            ArchModule(
                id=layer.id,
                name=layer.name,
                layer=layer.id,
                node_ids=layer.nodes,
                description=f"{layer.name} layer inferred from repository structure.",
                file_count=sum(len(node.files) for node in nodes if node.id in layer.nodes),
            )
            for layer in layers
        ]
        return ArchitectureResponse(
            repository_id=record.id,
            repository_name=record.name,
            architecture_type=self._architecture_type(meta),
            detected_layers=layers,
            nodes=nodes,
            edges=edges,
            modules=modules,
            request_flow=self._request_flow(),
            summary=ArchitectureSummary(
                language=meta.get("language", "Unknown"),
                framework=meta.get("framework", "Unknown"),
                total_modules=len(modules),
                total_nodes=len(nodes),
                entry_point=meta.get("entryPoint") or "/",
                architecture_pattern=self._architecture_type(meta),
            ),
        )

    def _file_paths(self, record: RepositoryRecord) -> list[str]:
        result: list[str] = []

        def walk(nodes: list[dict]) -> None:
            for node in nodes:
                if node.get("type") == "file":
                    result.append(node.get("path", ""))
                walk(node.get("children") or [])

        walk(record.file_tree or [])
        return result

    def _nodes_for_paths(self, paths: list[str]) -> list[ArchNode]:
        groups = [
            ("entry-point", "Entry Point", "frontend", "presentation", [path for path in paths if path.endswith(("main.tsx", "main.ts", "main.py", "app.py"))]),
            ("api", "API Layer", "controller", "presentation", [path for path in paths if "/api/" in path or "/routes/" in path]),
            ("services", "Services", "service", "business-logic", [path for path in paths if "/services/" in path]),
            ("models", "Models", "models", "domain", [path for path in paths if "/models/" in path or "/schemas/" in path or "/types/" in path]),
            ("repositories", "Repositories", "repository", "infrastructure", [path for path in paths if "/repositories/" in path]),
            ("configuration", "Configuration", "configuration", "infrastructure", [path for path in paths if path.split("/")[-1] in {"package.json", "pyproject.toml", "Dockerfile", "docker-compose.yml", "tsconfig.json"}]),
            ("tests", "Tests", "utilities", "infrastructure", [path for path in paths if "test" in path.lower()]),
        ]
        nodes: list[ArchNode] = []
        for node_id, name, node_type, layer, files in groups:
            if not files and node_id not in {"entry-point", "configuration"}:
                continue
            nodes.append(
                ArchNode(
                    id=node_id,
                    name=name,
                    type=node_type,  # type: ignore[arg-type]
                    description=f"{name} inferred from repository file structure.",
                    responsibilities=[f"Owns {name.lower()} concerns"],
                    files=files[:25],
                    dependencies=[],
                    dependents=[],
                    estimated_complexity="medium" if len(files) > 10 else "low",
                    estimated_lines=max(len(files) * 80, 20),
                    tags=[layer, node_id],
                    layer=layer,
                )
            )
        if not nodes:
            nodes.append(
                ArchNode(
                    id="repository",
                    name="Repository",
                    type="shared-library",
                    description="Repository structure could not be classified into known modules.",
                    responsibilities=["Source code"],
                    files=paths[:25],
                    dependencies=[],
                    dependents=[],
                    estimated_complexity="medium",
                    estimated_lines=len(paths) * 80,
                    tags=["repository"],
                    layer="presentation",
                )
            )
        return nodes

    def _edges_for_nodes(self, nodes: list[ArchNode]) -> list[ArchEdge]:
        ids = {node.id for node in nodes}
        candidates = [
            ("entry-point", "api"),
            ("api", "services"),
            ("services", "repositories"),
            ("services", "models"),
            ("repositories", "models"),
            ("tests", "services"),
        ]
        edges = [
            ArchEdge(id=f"{source}->{target}", source=source, target=target, type="dependency", label="uses")
            for source, target in candidates
            if source in ids and target in ids
        ]
        for edge in edges:
            source = next(node for node in nodes if node.id == edge.source)
            target = next(node for node in nodes if node.id == edge.target)
            source.dependencies.append(target.id)
            target.dependents.append(source.id)
        return edges

    def _layers_for_nodes(self, nodes: list[ArchNode]) -> list[ArchLayer]:
        order = {"presentation": 0, "business-logic": 1, "domain": 2, "infrastructure": 3}
        layers: dict[str, list[str]] = {}
        for node in nodes:
            layers.setdefault(node.layer, []).append(node.id)
        return [
            ArchLayer(id=layer, name=layer.replace("-", " ").title(), order=order.get(layer, 99), nodes=node_ids)
            for layer, node_ids in sorted(layers.items(), key=lambda item: order.get(item[0], 99))
        ]

    def _architecture_type(self, meta: dict) -> str:
        framework = meta.get("framework")
        if framework in {"React", "Next.js", "Vue"}:
            return "Client Application"
        if framework in {"FastAPI", "Django", "Flask"}:
            return "Backend Service"
        return "Repository Architecture"

    def _request_flow(self) -> list[RequestFlowStep]:
        return [
            RequestFlowStep(id="client", name="Client", type="frontend", description="Request enters the system.", details=["Browser or API client sends a request."]),
            RequestFlowStep(id="api", name="API Layer", type="controller", description="Route/controller handles input.", details=["Validate request", "Call service"]),
            RequestFlowStep(id="service", name="Service Layer", type="service", description="Business logic executes.", details=["Coordinate repositories", "Transform data"]),
            RequestFlowStep(id="repository", name="Repository Layer", type="repository", description="Persistence or source files are accessed.", details=["Read or write data"]),
        ]
