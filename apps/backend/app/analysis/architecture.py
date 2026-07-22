import posixpath

from app.intelligence.engine import RepositoryIntelligenceEngine
from app.intelligence.query_service import (
    ARCHITECTURE_RELATIONSHIP_EDGE_TYPES,
    ArchitectureSnapshotFacts,
    SnapshotQueryService,
)
from app.intelligence.models import RepositoryModule
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiDiagnostic, RiEvidence, RiNode
from app.schemas.architecture import (
    ArchEdge,
    ArchEvidence,
    ArchLayer,
    ArchModule,
    ArchitectureResponse,
    ArchitectureDiagnostic,
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
    def __init__(
        self,
        intelligence: RepositoryIntelligenceEngine | None = None,
        snapshots: SnapshotQueryService | None = None,
    ) -> None:
        self.intelligence = intelligence or RepositoryIntelligenceEngine()
        self.snapshots = snapshots

    def build_architecture(self, record: RepositoryRecord) -> ArchitectureResponse:
        # Architecture requests are persisted-data reads. ``from_record`` has a
        # legacy compatibility fallback that rebuilds from ``local_path``; using
        # it here would make a read endpoint depend on the working tree.
        repository_intelligence = self.intelligence.load(record)
        modules = (repository_intelligence.modules if repository_intelligence is not None else []) or [
            RepositoryModule(
                id="module:repository",
                name="Repository",
                role="unknown",
                layer="shared",
                path_prefix="/",
                files=(
                    [file.path for file in repository_intelligence.files]
                    if repository_intelligence is not None
                    else self._persisted_file_paths(record.file_tree or [])
                ),
                symbols=[],
                dependencies=[],
            )
        ]
        frameworks = repository_intelligence.discovery.frameworks if repository_intelligence is not None else []
        primary_language = (
            repository_intelligence.discovery.primary_language if repository_intelligence is not None else "Unknown"
        )
        entry_points = repository_intelligence.discovery.entry_points if repository_intelligence is not None else []
        module_paths = {self._normalize_path(path) for module in modules for path in module.files}
        facts = (
            self.snapshots.architecture_facts(record.id, module_paths=module_paths)
            if self.snapshots is not None
            else None
        )
        nodes = self._nodes_for_modules(modules)
        nodes.extend(self._dependency_nodes(facts))
        edges, diagnostics, unresolved_node_ids, covered_paths = self._edges_for_modules(modules, nodes, facts)
        edge_endpoint_ids = {node_id for edge in edges for node_id in (edge.source, edge.target)}
        nodes = [node for node in nodes if node.layer != "external" or node.id in edge_endpoint_ids]
        remaining_node_ids = {node.id for node in nodes}
        for diagnostic in diagnostics:
            if diagnostic.node_ids is not None:
                diagnostic.node_ids = [node_id for node_id in diagnostic.node_ids if node_id in remaining_node_ids] or None
        self._set_relationship_states(modules, nodes, edges, unresolved_node_ids, covered_paths, facts is not None)
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
            architecture_type=self._architecture_type(frameworks),
            detected_layers=layers,
            nodes=nodes,
            edges=edges,
            modules=arch_modules,
            request_flow=self._request_flow(modules),
            summary=ArchitectureSummary(
                language=primary_language,
                framework=frameworks[0] if frameworks else "Unknown",
                total_modules=len(arch_modules),
                total_nodes=len(nodes),
                entry_point=entry_points[0] if entry_points else "/",
                architecture_pattern=self._architecture_type(frameworks),
            ),
            relationship_snapshot_id=facts.snapshot.snapshot_id if facts is not None else None,
            diagnostics=diagnostics,
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

    def _persisted_file_paths(self, tree: list[dict]) -> list[str]:
        paths: list[str] = []
        for item in tree:
            if item.get("type") == "file" and isinstance(item.get("path"), str):
                paths.append(item["path"])
            children = item.get("children")
            if isinstance(children, list):
                paths.extend(self._persisted_file_paths(children))
        return sorted(set(paths))

    def _dependency_nodes(self, facts: ArchitectureSnapshotFacts | None) -> list[ArchNode]:
        if facts is None:
            return []
        relationship_keys = {
            key
            for edge in facts.edges
            if edge.predicate in ARCHITECTURE_RELATIONSHIP_EDGE_TYPES
            for key in (edge.subject_key, edge.object_key)
        }
        result: list[ArchNode] = []
        for item in facts.nodes:
            if item.node_kind != "dependency" or item.stable_key not in relationship_keys:
                continue
            evidence = facts.node_evidence.get(item.id, [])
            result.append(
                ArchNode(
                    id=item.stable_key,
                    name=item.name or item.stable_key,
                    type="shared-library",
                    description="External dependency from resolved repository evidence.",
                    responsibilities=["Provides an externally declared or imported capability"],
                    files=sorted({entry.path for entry in evidence}),
                    dependencies=[],
                    dependents=[],
                    estimated_complexity="low",
                    estimated_lines=0,
                    tags=["external", "dependency"],
                    layer="external",
                )
            )
        return result

    def _edges_for_modules(
        self,
        modules: list[RepositoryModule],
        nodes: list[ArchNode],
        facts: ArchitectureSnapshotFacts | None,
    ) -> tuple[list[ArchEdge], list[ArchitectureDiagnostic], set[str], set[str]]:
        if facts is None:
            return (
                [],
                [
                    ArchitectureDiagnostic(
                        code="ARCH-REL-NOT-EXTRACTED",
                        category="relationship extraction",
                        severity="info",
                        message="No sealed repository-intelligence snapshot is available for relationship analysis.",
                    )
                ],
                set(),
                set(),
            )

        module_by_id = {module.id: module for module in modules}
        modules_by_file: dict[str, list[str]] = {}
        for module in modules:
            for path in module.files:
                modules_by_file.setdefault(self._normalize_path(path), []).append(module.id)
        snapshot_node_by_key = {item.stable_key: item for item in facts.nodes}
        node_ids = {node.id for node in nodes}
        diagnostics = [self._architecture_diagnostic(item, modules_by_file, node_ids) for item in facts.diagnostics]
        unresolved_node_ids: set[str] = set()
        # Inventory-only file nodes prove that a path exists, not that a
        # relationship-capable extractor ran. Count only evidence emitted by a
        # syntax/manifest producer so unsupported files cannot look isolated.
        covered_paths = facts.covered_paths

        for item in facts.diagnostics:
            if item.code not in {"RI-RES-UNRESOLVED", "RI-RES-AMBIGUOUS"}:
                continue
            if item.path:
                unresolved_node_ids.update(modules_by_file.get(self._normalize_path(item.path), []))
            for key in (item.subject_key, item.object_key):
                if key in node_ids:
                    unresolved_node_ids.add(key)

        edges: list[ArchEdge] = []
        for fact in facts.edges:
            if fact.predicate not in ARCHITECTURE_RELATIONSHIP_EDGE_TYPES:
                continue
            evidence_rows = facts.edge_evidence.get(fact.id, [])
            source_ids = self._architecture_endpoint_ids(
                fact.subject_kind,
                fact.subject_key,
                evidence_rows,
                modules_by_file,
                module_by_id,
                snapshot_node_by_key,
                facts,
                is_subject=True,
            )
            target_ids = self._architecture_endpoint_ids(
                fact.object_kind,
                fact.object_key,
                evidence_rows,
                modules_by_file,
                module_by_id,
                snapshot_node_by_key,
                facts,
                is_subject=False,
            )
            root_scope_evidence = [
                item
                for item in evidence_rows
                if fact.predicate == "depends_on"
                and fact.subject_kind == "repository"
                and not posixpath.dirname(self._normalize_path(item.path))
            ]
            if root_scope_evidence:
                diagnostics.append(
                    ArchitectureDiagnostic(
                        code="ARCH-REL-REPO-SCOPED",
                        category="relationship mapping",
                        severity="info",
                        message="A repository-root dependency declaration is kept repository-scoped and is not attributed to modules.",
                        path=root_scope_evidence[0].path,
                        start_line=root_scope_evidence[0].start_line,
                        end_line=root_scope_evidence[0].end_line,
                        subject_key=fact.subject_key,
                        object_key=fact.object_key,
                        details={"factId": fact.edge_id, "predicate": fact.predicate},
                        node_ids=[fact.object_key] if fact.object_key in node_ids else None,
                    )
                )
                if len(root_scope_evidence) == len(evidence_rows):
                    continue
            pairs = sorted(
                (source, target)
                for source in source_ids
                for target in target_ids
                if source in node_ids and target in node_ids
            )
            non_self_pairs = [(source, target) for source, target in pairs if source != target]
            if pairs and not non_self_pairs:
                # A resolved fact wholly inside one architecture module remains
                # extraction evidence, but it is not a module-to-module edge.
                continue
            if not non_self_pairs:
                diagnostics.append(
                    ArchitectureDiagnostic(
                        code="ARCH-REL-ENDPOINT-UNMAPPED",
                        category="relationship mapping",
                        severity="warning",
                        message="A resolved relationship could not be mapped to architecture nodes without guessing.",
                        path=evidence_rows[0].path if evidence_rows else None,
                        start_line=evidence_rows[0].start_line if evidence_rows else None,
                        end_line=evidence_rows[0].end_line if evidence_rows else None,
                        subject_key=fact.subject_key,
                        object_key=fact.object_key,
                        details={"factId": fact.edge_id, "predicate": fact.predicate},
                        node_ids=sorted(source_ids | target_ids) or None,
                    )
                )
                unresolved_node_ids.update(source_ids | target_ids)
                continue
            citations = [
                ArchEvidence(
                    snapshot_id=facts.snapshot.snapshot_id,
                    fact_id=fact.edge_id,
                    path=item.path,
                    start_line=item.start_line,
                    end_line=item.end_line,
                )
                for item in evidence_rows
            ]
            for index, (source, target) in enumerate(non_self_pairs, start=1):
                edge_id = fact.edge_id if len(non_self_pairs) == 1 else f"{fact.edge_id}:{index}"
                edges.append(
                    ArchEdge(
                        id=edge_id,
                        source=source,
                        target=target,
                        type=ARCHITECTURE_RELATIONSHIP_EDGE_TYPES[fact.predicate],  # type: ignore[arg-type]
                        label=fact.predicate.replace("_", " "),
                        predicate=fact.predicate,
                        truth_class="inferred",
                        evidence=citations,
                    )
                )

        node_by_id = {node.id: node for node in nodes}
        for edge in edges:
            source = node_by_id[edge.source]
            target = node_by_id[edge.target]
            if target.id not in source.dependencies:
                source.dependencies.append(target.id)
            if source.id not in target.dependents:
                target.dependents.append(source.id)
        for node in nodes:
            node.dependencies.sort()
            node.dependents.sort()
        return edges, diagnostics, unresolved_node_ids, covered_paths

    def _architecture_endpoint_ids(
        self,
        node_kind: str,
        stable_key: str,
        edge_evidence: list[RiEvidence],
        modules_by_file: dict[str, list[str]],
        module_by_id: dict[str, RepositoryModule],
        snapshot_node_by_key: dict[str, RiNode],
        facts: ArchitectureSnapshotFacts,
        *,
        is_subject: bool,
    ) -> set[str]:
        if node_kind == "dependency":
            return {stable_key}
        if node_kind == "repository":
            return self._modules_for_evidence_scope(edge_evidence, module_by_id)

        path = self._path_for_stable_key(node_kind, stable_key)
        if path is not None and node_kind != "module":
            return set(modules_by_file.get(path, []))

        evidence = edge_evidence if is_subject else []
        node = snapshot_node_by_key.get(stable_key)
        if node is not None and not evidence:
            evidence = facts.node_evidence.get(node.id, [])
        exact = {
            module_id
            for item in evidence
            for module_id in modules_by_file.get(self._normalize_path(item.path), [])
        }
        if exact:
            return exact
        if path is not None:
            return {
                module.id
                for module in module_by_id.values()
                if any(self._path_is_within(self._normalize_path(file_path), path) for file_path in module.files)
            }
        return set()

    def _modules_for_evidence_scope(
        self,
        evidence: list[RiEvidence],
        module_by_id: dict[str, RepositoryModule],
    ) -> set[str]:
        result: set[str] = set()
        for item in evidence:
            path = self._normalize_path(item.path)
            directory = posixpath.dirname(path)
            if not directory:
                continue
            for module in module_by_id.values():
                if any(
                    self._path_is_within(self._normalize_path(file_path), directory)
                    for file_path in module.files
                ):
                    result.add(module.id)
        return result

    def _set_relationship_states(
        self,
        modules: list[RepositoryModule],
        nodes: list[ArchNode],
        edges: list[ArchEdge],
        unresolved_node_ids: set[str],
        covered_paths: set[str],
        snapshot_available: bool,
    ) -> None:
        connected = {node_id for edge in edges for node_id in (edge.source, edge.target)}
        module_by_id = {module.id: module for module in modules}
        for node in nodes:
            if node.id in connected:
                node.relationship_state = "connected"
            elif node.id in unresolved_node_ids:
                node.relationship_state = "unresolved"
            elif node.id in module_by_id and snapshot_available and module_by_id[node.id].files and all(
                self._normalize_path(path) in covered_paths for path in module_by_id[node.id].files
            ):
                node.relationship_state = "no-observed-relationships"
            else:
                node.relationship_state = "not-extracted"

    def _architecture_diagnostic(
        self,
        item: RiDiagnostic,
        modules_by_file: dict[str, list[str]],
        node_ids: set[str],
    ) -> ArchitectureDiagnostic:
        attributed_node_ids: set[str] = set()
        if item.path:
            attributed_node_ids.update(modules_by_file.get(self._normalize_path(item.path), []))
        for key in (item.subject_key, item.object_key):
            if key is None:
                continue
            if key in node_ids:
                attributed_node_ids.add(key)
                continue
            path = self._path_for_stable_key("file" if key.startswith("file:") else "symbol", key)
            if path is not None:
                attributed_node_ids.update(modules_by_file.get(path, []))
        return ArchitectureDiagnostic(
            code=item.code,
            category=item.category,
            severity=item.severity,
            message=item.message,
            path=item.path,
            start_line=item.span_start_line,
            end_line=item.span_end_line,
            subject_key=item.subject_key,
            object_key=item.object_key,
            details=dict(item.details) if item.details is not None else None,
            node_ids=sorted(attributed_node_ids) or None,
        )

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path.replace("\\", "/").lstrip("/")

    @classmethod
    def _path_for_stable_key(cls, node_kind: str, stable_key: str) -> str | None:
        if node_kind == "file" and stable_key.startswith("file:"):
            return cls._normalize_path(stable_key.removeprefix("file:"))
        if node_kind == "symbol" and "::" in stable_key:
            return cls._normalize_path(stable_key.split("::", 1)[0])
        if node_kind == "module" and stable_key.startswith("mod:"):
            return cls._normalize_path(stable_key.removeprefix("mod:"))
        return None

    @staticmethod
    def _path_is_within(path: str, directory: str) -> bool:
        return not directory or path == directory or path.startswith(f"{directory}/")

    def _layers_for_nodes(self, nodes: list[ArchNode]) -> list[ArchLayer]:
        order = {"presentation": 0, "business-logic": 1, "domain": 2, "infrastructure": 3, "shared": 4, "external": 5}
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
