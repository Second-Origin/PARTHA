import posixpath
import re
from collections import Counter, defaultdict

from app.extraction.lockfiles import SUPPORTED_LOCKFILE_FILENAMES
from app.extraction.manifests import SUPPORTED_MANIFEST_FILENAMES
from app.intelligence.classification import LAYER_ORDER, layer_for_role
from app.intelligence.query_service import (
    ARCHITECTURE_DIAGNOSTIC_CODES,
    ARCHITECTURE_RELATIONSHIP_EDGE_TYPES,
    ArchitectureSnapshotFacts,
    SnapshotQueryService,
)
from app.insights.relationship_diagnostics import (
    UnresolvedRelationshipContext,
    is_external_unresolved,
    load_unresolved_relationship_context,
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
    "entrypoint": "entrypoint",
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
    "middleware": "middleware",
    "documentation": "shared-library",
    "unknown": "shared-library",
}

_FRAMEWORK_BY_DEPENDENCY_NAME = {
    "react": "React",
    "next": "Next.js",
    "vue": "Vue",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
}


_SYMBOL_DISAMBIGUATOR = re.compile(r"#\d+$")


def _display_symbol(qualified: str) -> str:
    """Strip the uniqueness suffix a stable key carries for repeated names.

    Two `@overload`-style definitions of the same name in one file are distinct
    nodes, so their keys are disambiguated (``group#5``). That suffix is an
    identity detail, not part of what the code calls the symbol.
    """

    return _SYMBOL_DISAMBIGUATOR.sub("", qualified)


class ArchitectureAnalyzer:
    """Builds the Architecture read model exclusively from sealed ri.v1 snapshots.

    No filesystem read, no working-tree fallback, and no legacy
    ``repo_metadata['intelligence']`` or ``record.file_tree`` read: every field
    is derived from :class:`SnapshotQueryService` facts. A repository with no
    sealed snapshot for its current revision raises ``NotFoundError`` (#217),
    the same 404 contract Dependencies, Review and Insights already use —
    never a fallback graph built from unsealed repository metadata.
    """

    def __init__(self, snapshots: SnapshotQueryService | None = None) -> None:
        self.snapshots = snapshots

    def build_architecture(self, record: RepositoryRecord) -> ArchitectureResponse:
        if self.snapshots is not None:
            self.snapshots.require_sealed_snapshot_for_current_revision(record.id)
        facts = self.snapshots.architecture_facts(record.id) if self.snapshots is not None else None
        modules = self._modules_from_facts(facts)
        frameworks = self._frameworks_from_facts(facts)
        primary_language = self._primary_language_from_facts(facts)
        entry_points = self._entry_points_from_facts(facts)
        nodes = self._nodes_for_modules(modules)
        nodes.extend(self._dependency_nodes(facts))
        edges, diagnostics, unresolved_node_ids, covered_paths = self._edges_for_modules(modules, nodes, facts)
        edge_endpoint_ids = {node_id for edge in edges for node_id in (edge.source, edge.target)}
        nodes = [node for node in nodes if node.layer != "external" or node.id in edge_endpoint_ids]
        remaining_node_ids = {node.id for node in nodes}
        for diagnostic in diagnostics:
            if diagnostic.node_ids is not None:
                diagnostic.node_ids = [
                    node_id for node_id in diagnostic.node_ids if node_id in remaining_node_ids
                ] or None
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
                    description=self._module_description(module),
                    responsibilities=self._module_responsibilities(module),
                    files=module.files[:25],
                    dependencies=[],
                    dependents=[],
                    # No producer measures size/complexity (#217): file count is
                    # not a line count or a complexity metric, so it is never
                    # used to synthesize one.
                    estimated_complexity="not_computed",
                    estimated_lines="not_computed",
                    tags=[module.layer, module.role, module.id.replace("module:", "")],
                    layer=module.layer,
                )
            )
        return nodes

    @staticmethod
    def _module_description(module: RepositoryModule) -> str:
        """State what the snapshot observed, rather than restating the path.

        Every clause here is an observed fact already sealed in the snapshot:
        how many symbols the module defines, which of them a reader would
        recognise it by, and where it lives. Nothing is inferred about what
        the module is *for* -- that would be a guess, and an unsourced claim
        is exactly what this product does not make.
        """

        if not module.symbols:
            # No symbols observed is itself worth saying plainly, rather than
            # dressing the path up as a description.
            return f"{module.path_prefix} — no code symbols were extracted from this module."
        count = len(module.symbols)
        noun = "symbol" if count == 1 else "symbols"
        notable = ArchitectureAnalyzer._notable_symbols(module.symbols)
        if not notable:
            return f"Defines {count} {noun}."
        listed = ", ".join(notable)
        if count == len(notable):
            # Everything it defines is named, so "including" would understate it.
            return f"Defines {count} {noun}: {listed}."
        return f"Defines {count} {noun}, including {listed}."

    @staticmethod
    def _module_responsibilities(module: RepositoryModule) -> list[str]:
        """Observed properties of the module, not a guess at its purpose.

        The previous wording ("Owns unknown concerns") read as a statement
        about the code when it was really a statement about the classifier
        having no opinion. Where a role *was* classified it is reported as
        one; where it was not, the entry is omitted rather than asserted.
        """

        entries: list[str] = []
        if module.role and module.role != "unknown":
            entries.append(f"Classified as {module.role.replace('-', ' ')}")
        file_count = len(module.files)
        if file_count > 1:
            entries.append(f"{file_count} files")
        if module.symbols:
            entries.append(f"{len(module.symbols)} observed symbols")
        return entries

    def _empty_module(self, files: list[str]) -> list[RepositoryModule]:
        return [
            RepositoryModule(
                id="module:repository",
                name="Repository",
                role="unknown",
                layer="shared",
                path_prefix="/",
                files=files,
                symbols=[],
                dependencies=[],
            )
        ]

    def _file_roles(self, facts: ArchitectureSnapshotFacts) -> dict[str, str]:
        """Map file path -> role-classifier classification (#95), if any.

        A file with no ``classified_as`` assertion has no entry: absence here
        means "not classified", never a fabricated "unknown" guess.
        """

        roles: dict[str, str] = {}
        for assertion in facts.assertions:
            if assertion.predicate != "classified_as" or assertion.subject_kind != "file":
                continue
            classification = str((assertion.value or {}).get("classification", ""))
            if not classification:
                continue
            roles[assertion.subject_key.removeprefix("file:")] = classification
        return roles

    @staticmethod
    def _paths_in_relationships(facts: ArchitectureSnapshotFacts) -> set[str]:
        """Files that are one end of an observed architecture relationship.

        A file can be a real part of the system while defining nothing of its
        own -- a package initialiser that only re-exports, a barrel module.
        What makes it structural is that something resolved to it, or it
        resolved to something, and both of those are sealed edges.
        """

        paths: set[str] = set()
        for edge in facts.edges:
            for key in (edge.subject_key, edge.object_key):
                if key.startswith("file:"):
                    paths.add(key.removeprefix("file:"))
        return paths

    @staticmethod
    def _is_module_file(
        path: str,
        *,
        role: str | None,
        defines_symbols: bool,
        related_paths: set[str],
    ) -> bool:
        """Whether this file is part of the system's own structure (#444).

        A module has to be something the extraction actually saw: symbols it
        defines, a relationship it takes part in, or a role the snapshot
        classified it into (``documentation``, ``test``, ``controller``). A
        file that produced none of those is not being judged unimportant --
        nothing was observed about it, and inventing a module from a path is
        how `.gitignore` ended up sitting in the Shared layer beside the
        library itself.
        """

        if defines_symbols or path in related_paths:
            return True
        return role is not None and role != "unknown"

    def _symbols_by_file(self, facts: ArchitectureSnapshotFacts) -> dict[str, list[str]]:
        """Map file path -> names of the symbols that file defines.

        Symbol stable keys are ``<path>::<qualified name>`` (#217), so the
        owning file is read off the key rather than inferred. These are
        observed facts already sealed in the snapshot; nothing here computes
        or estimates anything.
        """

        symbols: dict[str, list[str]] = defaultdict(list)
        for stable_key in facts.symbol_keys:
            path, separator, qualified = stable_key.partition("::")
            if not separator or not path or not qualified:
                continue
            # Top-level definitions only. A method is defined by its class, not
            # by the module, and counting every one of them turns "what does
            # this module define" into a line-count proxy -- which is exactly
            # the kind of synthesized measure #217 rules out.
            if "." in qualified:
                continue
            symbols[path].append(_display_symbol(qualified))
        return {path: sorted(set(names)) for path, names in symbols.items()}

    @staticmethod
    def _notable_symbols(qualified_names: list[str], limit: int = 4) -> list[str]:
        """The symbols a reader would recognise the module by.

        The caller has already narrowed these to top-level definitions, so the
        only judgement left is the oldest convention there is: a leading
        underscore means the author did not mean it for the outside. Those are
        dropped unless they are all there is. Ordering is deterministic, so the
        same snapshot always renders the same description.
        """

        public = [name for name in qualified_names if not name.startswith("_")]
        chosen = public or qualified_names
        return sorted(chosen)[:limit]

    def _modules_from_facts(self, facts: ArchitectureSnapshotFacts | None) -> list[RepositoryModule]:
        if facts is None:
            # Defensive only: build_architecture requires a sealed snapshot
            # before calling this whenever self.snapshots is configured, so a
            # production caller never reaches this branch with real facts
            # unresolved. It stays as an honest, empty module set rather than
            # ever reading `record.file_tree` (unsealed repository metadata).
            return self._empty_module([])
        role_by_path = self._file_roles(facts)
        symbols_by_path = self._symbols_by_file(facts)
        related_paths = self._paths_in_relationships(facts)
        # Dependency-manifest and lockfile paths already surface as dependency
        # evidence (Dependency Graph) -- grouping them into an architecture
        # module too misrepresents `package.json`/`pyproject.toml` as a piece
        # of the system's own structure. #396 stopped there, which was right
        # but narrower than the defect: `.gitignore`, `.editorconfig`,
        # `LICENSE.txt` and `uv.lock` are neither manifests nor lockfiles, so
        # on `pallets/click` seven of the sixteen reported modules were not
        # code. `_is_module_file` is what closes that hole.
        _non_module_filenames = SUPPORTED_MANIFEST_FILENAMES + SUPPORTED_LOCKFILE_FILENAMES
        file_paths = sorted(
            path
            for path in (
                node.stable_key.removeprefix("file:")
                for node in facts.nodes
                if node.node_kind == "file" and node.stable_key.startswith("file:")
            )
            if posixpath.basename(path) not in _non_module_filenames
            and self._is_module_file(
                path,
                role=role_by_path.get(path),
                defines_symbols=bool(symbols_by_path.get(path)),
                related_paths=related_paths,
            )
        )
        if not file_paths:
            return self._empty_module([])
        grouped: dict[str, list[str]] = defaultdict(list)
        for path in file_paths:
            module_id = self._module_id(path, role_by_path.get(path), defines_symbols=bool(symbols_by_path.get(path)))
            grouped[module_id].append(path)
        modules: list[RepositoryModule] = []
        for module_id, paths in grouped.items():
            candidate_roles = [
                role_by_path[path]
                for path in paths
                if role_by_path.get(path) not in (None, "unknown", "documentation", "test")
            ]
            dominant = (
                Counter(candidate_roles).most_common(1)[0][0]
                if candidate_roles
                else (role_by_path.get(paths[0]) or "unknown")
            )
            modules.append(
                RepositoryModule(
                    id=module_id,
                    name=self._module_display_name(module_id),
                    role=dominant,  # type: ignore[arg-type]
                    layer=layer_for_role(dominant),
                    path_prefix=self._path_prefix(paths),
                    files=sorted(paths),
                    symbols=sorted({name for path in paths for name in symbols_by_path.get(path, [])}),
                    dependencies=[],
                )
            )
        return self._disambiguate_names(sorted(modules, key=lambda module: module.id))

    @staticmethod
    def _disambiguate_names(modules: list[RepositoryModule]) -> list[RepositoryModule]:
        """Qualify names that would otherwise collide.

        A repository can hold several modules called ``utils`` -- FastAPI has
        four. Rendering them all as "utils" tells the reader nothing about
        which is which, so a colliding name takes on as much of its parent
        path as it needs to become unique (``openapi/utils``,
        ``security/utils``). Names that are already unique are left alone, so
        the common case stays short.
        """

        by_name: dict[str, list[RepositoryModule]] = defaultdict(list)
        for module in modules:
            by_name[module.name].append(module)
        for name, colliding in by_name.items():
            if len(colliding) < 2:
                continue
            for module in colliding:
                qualifier = ArchitectureAnalyzer._qualifying_parent(module.id.removeprefix("module:"), name)
                if qualifier:
                    module.name = f"{qualifier}/{name}"
        return modules

    @staticmethod
    def _qualifying_parent(path: str, name: str) -> str:
        """The nearest ancestor directory that actually distinguishes ``path``.

        A directory named after the module it contains adds nothing:
        `examples/termui/termui.py` qualified by its immediate parent reads
        "termui/termui", which is noise where "examples/termui" is an answer.
        Walk up until the ancestor says something the name does not.
        """

        for segment in reversed(posixpath.dirname(path).split("/")):
            if segment and segment != name:
                return segment
        return ""

    @staticmethod
    def _module_id(path: str, role: str | None, *, defines_symbols: bool = False) -> str:
        parts = [part for part in path.strip("/").split("/") if part]
        if role in {"controller", "route"}:
            return "module:api"
        if role == "service":
            return "module:services"
        if role == "repository":
            return "module:repositories"
        if role in {"model", "dto", "interface", "enum"}:
            return "module:domain"
        if role == "middleware":
            return "module:middleware"
        if role == "configuration":
            return "module:configuration"
        if role == "test":
            return "module:tests"
        if role == "documentation":
            return "module:documentation"
        # A file that defines symbols is a module in its own right. Grouping
        # by the directory below the source root instead collapses a whole
        # package into one opaque node -- for a single-package repository that
        # is the entire library reduced to a single box, which is what this
        # branch used to do to every file under `src/<package>/`.
        if defines_symbols and parts:
            return f"module:{path.strip('/')}"
        if parts and parts[0] in {"app", "src", "backend", "frontend", "apps"} and len(parts) > 1:
            return f"module:{parts[1].lower()}"
        return f"module:{parts[0].lower() if parts else 'repository'}"

    @staticmethod
    def _module_display_name(module_id: str) -> str:
        raw = module_id.removeprefix("module:")
        if "/" in raw:
            # A per-file module id carries the path for uniqueness; the reader
            # wants the module's own name. `src/click/core.py` reads as `core`,
            # and a package initialiser reads as the package it opens.
            stem = posixpath.splitext(posixpath.basename(raw))[0]
            if stem in {"__init__", "index", "mod"}:
                parent = posixpath.basename(posixpath.dirname(raw))
                return parent or stem
            return stem
        if "." in raw:
            # `_module_id`'s fallback groups a top-level file with no
            # directory nesting by its own filename (e.g. "app.py") -- that
            # is a real filename, not a word slug, and Title Case corrupts
            # its extension ("app.py" -> "App.Py"). Render it verbatim.
            return raw
        return raw.replace("-", " ").title()

    @staticmethod
    def _path_prefix(paths: list[str]) -> str:
        if not paths:
            return "/"
        parts = [path.strip("/").split("/") for path in paths]
        prefix: list[str] = []
        for columns in zip(*parts):
            if len(set(columns)) == 1:
                prefix.append(columns[0])
            else:
                break
        return "/" + "/".join(prefix) if prefix else "/"

    def _frameworks_from_facts(self, facts: ArchitectureSnapshotFacts | None) -> list[str]:
        if facts is None:
            return []
        names = {node.name.lower() for node in facts.nodes if node.node_kind == "dependency" and node.name}
        return sorted(
            {
                framework
                for dependency_name, framework in _FRAMEWORK_BY_DEPENDENCY_NAME.items()
                if dependency_name in names
            }
        )

    def _primary_language_from_facts(self, facts: ArchitectureSnapshotFacts | None) -> str:
        if facts is None:
            return "Unknown"
        # Count persisted file facts, not symbols. Symbol counts make a file
        # with many declarations (and synthetic route symbols) outweigh other
        # files, and report "Unknown" for a valid script containing only
        # top-level statements.
        counts = Counter(node.language for node in facts.nodes if node.node_kind == "file" and node.language)
        if not counts:
            return "Unknown"
        dominant = counts.most_common(1)[0][0]
        return {"python": "Python", "typescript": "TypeScript"}.get(dominant, dominant.title())

    def _entry_points_from_facts(self, facts: ArchitectureSnapshotFacts | None) -> list[str]:
        if facts is None:
            return []
        role_by_path = self._file_roles(facts)
        return sorted(path for path, role in role_by_path.items() if role == "entrypoint")

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
                    estimated_complexity="not_computed",
                    estimated_lines="not_computed",
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

        # An RI-RES-UNRESOLVED whose target is a third-party dependency or the
        # language platform is not an unmapped *architecture* relationship -- it
        # should neither flag a module red nor crowd the diagnostics list.
        # Genuine in-repo gaps and every RI-RES-AMBIGUOUS still count. Same
        # #412 judgment Repository Insights uses; the raw resolver diagnostics
        # stay available via the intelligence evidence API.
        unresolved_ctx = (
            load_unresolved_relationship_context(self.snapshots.db, facts.snapshot.snapshot_id)
            if self.snapshots is not None
            else UnresolvedRelationshipContext.empty()
        )

        def _is_architecture_relevant(item: RiDiagnostic) -> bool:
            if item.code not in ARCHITECTURE_DIAGNOSTIC_CODES:
                return False
            if item.code != "RI-RES-UNRESOLVED":
                return True
            return not is_external_unresolved(item.path, (item.details or {}).get("observation_id"), unresolved_ctx)

        architecture_diagnostic_items = [item for item in facts.diagnostics if _is_architecture_relevant(item)]
        diagnostics = [
            self._architecture_diagnostic(item, modules_by_file, node_ids) for item in architecture_diagnostic_items
        ]
        unresolved_node_ids: set[str] = set()
        # Inventory-only file nodes prove that a path exists, not that a
        # relationship-capable extractor ran. Count only evidence emitted by a
        # syntax/manifest producer so unsupported files cannot look isolated.
        covered_paths = facts.covered_paths

        for item in architecture_diagnostic_items:
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
            module_id for item in evidence for module_id in modules_by_file.get(self._normalize_path(item.path), [])
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
                if any(self._path_is_within(self._normalize_path(file_path), directory) for file_path in module.files):
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
            elif (
                node.id in module_by_id
                and snapshot_available
                and module_by_id[node.id].files
                and all(self._normalize_path(path) in covered_paths for path in module_by_id[node.id].files)
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
        layers: dict[str, list[str]] = {}
        for node in nodes:
            layers.setdefault(node.layer, []).append(node.id)
        return [
            ArchLayer(
                id=layer,
                name=layer.replace("-", " ").title(),
                order=LAYER_ORDER.get(layer, 99),
                nodes=node_ids,
            )
            for layer, node_ids in sorted(layers.items(), key=lambda item: LAYER_ORDER.get(item[0], 99))
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
            RequestFlowStep(
                id="client",
                name="Client",
                type="frontend",
                description="Request enters the system.",
                details=["Browser or API client sends a request."],
            ),
        ]
        if "route" in module_roles or "controller" in module_roles:
            steps.append(
                RequestFlowStep(
                    id="api",
                    name="API Layer",
                    type="controller",
                    description="Route/controller handles input.",
                    details=["Validate request", "Call service"],
                )
            )
        if "service" in module_roles:
            steps.append(
                RequestFlowStep(
                    id="service",
                    name="Service Layer",
                    type="service",
                    description="Business logic executes.",
                    details=[
                        "Coordinate repository intelligence consumers",
                        "Transform data",
                    ],
                )
            )
        if "repository" in module_roles:
            steps.append(
                RequestFlowStep(
                    id="repository",
                    name="Repository Layer",
                    type="repository",
                    description="Persistence or source files are accessed.",
                    details=["Read or write data"],
                )
            )
        return steps
