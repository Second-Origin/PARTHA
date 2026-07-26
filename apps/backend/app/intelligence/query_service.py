"""Read-only, owner-scoped queries over sealed ``ri.v1`` snapshots (#92)."""

from collections import defaultdict
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, UnsupportedSchemaVersionError
from app.models.snapshot import (
    RiAssertion,
    RiDerivation,
    RiDiagnostic,
    RiEdge,
    RiEvidence,
    RiNode,
    RiObservation,
    RiSnapshot,
)


#: Predicates Architecture renders, mapped to the architecture edge type.
ARCHITECTURE_RELATIONSHIP_EDGE_TYPES = {
    "imports": "import",
    "calls": "calls",
    "routes_to": "api-call",
    "implements": "dependency",
    "depends_on": "dependency",
}
#: Predicates the authentication explanation walks to build guard chains. It
#: shares ``architecture_facts`` with Architecture but needs ``injects``, which
#: Architecture never draws.
AUTHENTICATION_EXPLANATION_PREDICATES = frozenset({"injects", "calls", "routes_to"})
#: What ``architecture_facts`` actually loads: the union of both consumers.
#: Each consumer still filters again in Python for what it renders, so widening
#: this set never widens a response — it only prevents starving a consumer.
ARCHITECTURE_FACT_PREDICATES = (
    frozenset(ARCHITECTURE_RELATIONSHIP_EDGE_TYPES) | AUTHENTICATION_EXPLANATION_PREDICATES
)
ARCHITECTURE_DIAGNOSTIC_CODES = frozenset({"RI-RES-UNRESOLVED", "RI-RES-AMBIGUOUS"})
#: Diagnostic codes the authentication explanation renders.
AUTHENTICATION_DIAGNOSTIC_CODES = frozenset(
    {"RI-RES-UNRESOLVED", "RI-RES-AMBIGUOUS", "RI-EXT-UNSUPPORTED", "RI-SRC-MALFORMED"}
)
#: Union of diagnostic codes loaded for both consumers.
ARCHITECTURE_FACT_DIAGNOSTIC_CODES = ARCHITECTURE_DIAGNOSTIC_CODES | AUTHENTICATION_DIAGNOSTIC_CODES
#: Node kinds the architecture consumer always needs, independent of whether the
#: node participates in a relationship edge. ``symbol`` is deliberately absent:
#: symbols are loaded only when an edge references them.
ARCHITECTURE_NODE_KINDS = frozenset({"file", "dependency", "repository"})
#: The only assertion predicate the architecture consumer reads (file role
#: classification). Others stay in the snapshot and are simply not loaded here.
ARCHITECTURE_ASSERTION_PREDICATES = frozenset({"classified_as"})
#: Upper bound on ids bound into a single ``IN`` clause. SQLite caps bound
#: parameters per statement (999 before 3.32, 32766 after), so any read whose
#: id set grows with repository size must be split into batches rather than
#: trusting the set to stay small.
SNAPSHOT_IN_CLAUSE_BATCH_SIZE = 500
ARCHITECTURE_EVIDENCE_BATCH_SIZE = SNAPSHOT_IN_CLAUSE_BATCH_SIZE


def batched_ids[T](values: Sequence[T], size: int = SNAPSHOT_IN_CLAUSE_BATCH_SIZE) -> Iterator[list[T]]:
    """Yield ``values`` in ``size``-sized lists for bounded ``IN`` clauses."""

    for start in range(0, len(values), size):
        yield list(values[start : start + size])


@dataclass(frozen=True)
class ArchitectureSnapshotFacts:
    """Persisted facts needed to build evidence-backed architecture relationships."""

    snapshot: RiSnapshot
    nodes: list[RiNode]
    edges: list[RiEdge]
    assertions: list[RiAssertion]
    node_evidence: dict[int, list[RiEvidence]]
    edge_evidence: dict[int, list[RiEvidence]]
    diagnostics: list[RiDiagnostic]
    covered_paths: set[str]


@dataclass(frozen=True)
class SnapshotFileFact:
    path: str
    language: str | None
    role: str | None
    role_confidence: str | None


@dataclass(frozen=True)
class SnapshotDependencyDeclaration:
    version: str | None
    dependency_type: str | None
    manifest_path: str | None
    workspace_path: str | None
    start_line: int | None
    end_line: int | None
    extractor: str | None
    extractor_version: str | None


@dataclass(frozen=True)
class SnapshotDependencyFact:
    stable_key: str
    name: str
    ecosystem: str | None
    declarations: tuple[SnapshotDependencyDeclaration, ...]


@dataclass(frozen=True)
class SnapshotRouteFact:
    path: str
    evidence_paths: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotModuleFact:
    name: str
    role: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class ProductSnapshotProjection:
    """Immutable, bounded projection shared by Documentation and free-form AI."""

    snapshot_id: str
    schema_version: str
    repository_id: str
    revision_kind: str
    revision_value: str
    revision_ref: str | None
    canonical_graph_hash: str
    primary_language: str
    frameworks: tuple[str, ...]
    entry_points: tuple[str, ...]
    modules: tuple[SnapshotModuleFact, ...]
    files: tuple[SnapshotFileFact, ...]
    dependencies: tuple[SnapshotDependencyFact, ...]
    routes: tuple[SnapshotRouteFact, ...]
    diagnostics: tuple[tuple[str, str, str | None], ...]


class SnapshotQueryService:
    """Expose only persisted snapshot facts; this service never touches repository storage."""

    def __init__(self, db: Session, owner_id: str) -> None:
        self.db = db
        self.owner_id = owner_id

    supported_schema_versions = ("ri.v1",)

    def metadata(self, snapshot_id: str) -> RiSnapshot:
        return self._snapshot(snapshot_id)

    def has_evidence_reference(
        self,
        snapshot: RiSnapshot,
        fact_id: str,
        path: str,
        start_line: int,
        end_line: int,
    ) -> bool:
        """Whether the exact fact citation exists in this snapshot's evidence.

        A client-controlled deep link must not be able to keep a genuine
        snapshot/span while substituting a different fact (or vice versa) and
        still receive a verified citation response.
        """

        count = self.db.scalar(
            select(func.count())
            .select_from(RiEvidence)
            .outerjoin(
                RiNode,
                and_(
                    RiNode.snapshot_id == RiEvidence.snapshot_id,
                    RiNode.id == RiEvidence.node_ref,
                ),
            )
            .outerjoin(
                RiEdge,
                and_(
                    RiEdge.snapshot_id == RiEvidence.snapshot_id,
                    RiEdge.id == RiEvidence.edge_ref,
                ),
            )
            .outerjoin(
                RiObservation,
                and_(
                    RiObservation.snapshot_id == RiEvidence.snapshot_id,
                    RiObservation.id == RiEvidence.observation_ref,
                ),
            )
            .where(
                RiEvidence.snapshot_id == snapshot.snapshot_id,
                RiEvidence.path == path,
                RiEvidence.start_line == start_line,
                RiEvidence.end_line == end_line,
                or_(
                    RiNode.stable_key == fact_id,
                    RiEdge.edge_id == fact_id,
                    RiObservation.observation_id == fact_id,
                ),
            )
        )
        return bool(count)

    def source_content_hash(self, snapshot: RiSnapshot, path: str) -> str | None:
        """Return the sealed byte hash for a snapshot file, if one exists."""

        node = self.db.scalars(
            select(RiNode).where(
                RiNode.snapshot_id == snapshot.snapshot_id,
                RiNode.node_kind == "file",
                RiNode.stable_key == f"file:{path}",
            )
        ).first()
        value = (node.properties or {}).get("content_sha256") if node is not None else None
        return value if isinstance(value, str) else None

    def latest_snapshot_for_owner(self, repository_id: str) -> RiSnapshot | None:
        """Newest sealed snapshot for an owner-scoped repository, or ``None``.

        Public entry point for consumers that need snapshot identity rather
        than snapshot facts (#113). Owner scoping and the sealed-state filter
        are the same ones every other consumer query uses.
        """

        return self._latest_snapshot(repository_id)

    def require_sealed_snapshot_for_current_revision(self, repository_id: str) -> RiSnapshot:
        """Newest sealed snapshot bound to the repository's *current* revision.

        Every product surface that publishes snapshot identity must agree on
        which snapshot it is describing. Resolving "latest sealed" alone is not
        enough: after a re-import the newest sealed snapshot can belong to the
        previous revision, and a surface that rendered it would present stale
        facts under the current revision's name. Consumers therefore share this
        one resolution, so Architecture, Review, Insights and the revision
        manifest cannot disagree about the revision under review.

        Raises ``NotFoundError`` rather than returning ``None`` so a repository
        owned by someone else stays indistinguishable from one that has never
        been analysed.
        """

        from app.models.repository import RepositoryRecord

        snapshot = self._latest_snapshot(repository_id)
        if snapshot is None:
            raise NotFoundError(
                "No sealed Repository Intelligence snapshot is available for this repository.",
                {"repositoryId": repository_id},
            )
        record = self.db.get(RepositoryRecord, repository_id)
        if (
            record is None
            or snapshot.repository_id != record.id
            or snapshot.revision_kind != record.revision_kind
            or snapshot.revision_value != record.revision_value
        ):
            # Fail closed even if persistence constraints are bypassed or a test
            # double supplies mismatched facts.
            raise NotFoundError(
                "The sealed snapshot does not match the selected repository revision.",
                {"repositoryId": repository_id, "snapshotId": snapshot.snapshot_id},
            )
        if snapshot.canonical_graph_hash is None or snapshot.sealed_at is None:
            raise NotFoundError(
                "The selected repository revision has no sealed snapshot.",
                {"repositoryId": repository_id},
            )
        return snapshot

    def sealed_snapshot_for_owner(self, repository_id: str, snapshot_id: str) -> RiSnapshot | None:
        """One named sealed snapshot of an owner-scoped repository, or ``None``.

        Verification needs the snapshot a submitted manifest actually names, not
        whichever snapshot happens to be newest, so an authentic manifest for a
        superseded revision can be recognised as authentic.
        """

        from app.models.repository import RepositoryRecord

        snapshot = self.db.scalars(
            select(RiSnapshot)
            .join(RepositoryRecord, RepositoryRecord.id == RiSnapshot.repository_id)
            .where(
                RiSnapshot.repository_id == repository_id,
                RiSnapshot.snapshot_id == snapshot_id,
                RiSnapshot.state == "completed",
                RepositoryRecord.owner_id == self.owner_id,
            )
        ).first()
        if snapshot is not None and snapshot.schema_version not in self.supported_schema_versions:
            raise UnsupportedSchemaVersionError(
                f"Unsupported snapshot schema version: {snapshot.schema_version}.",
                details={"received": snapshot.schema_version, "supported": list(self.supported_schema_versions)},
            )
        return snapshot

    def architecture_facts(self, repository_id: str) -> ArchitectureSnapshotFacts | None:
        """Return the newest sealed snapshot facts for an owner-scoped repository.

        This internal consumer query uses the normalized store behind the public
        #92 endpoints. ``None`` means no sealed snapshot is available; it is not
        evidence that the repository has no relationships.
        """

        snapshot = self._latest_snapshot(repository_id)
        if snapshot is None:
            return None
        edges = list(
            self.db.scalars(
                select(RiEdge)
                .where(
                    RiEdge.snapshot_id == snapshot.snapshot_id,
                    RiEdge.predicate.in_(ARCHITECTURE_FACT_PREDICATES),
                )
                .order_by(RiEdge.subject_key, RiEdge.predicate, RiEdge.object_key, RiEdge.edge_id, RiEdge.id)
            ).all()
        )
        # The architecture consumer needs every file node (module inventory and
        # primary language), every dependency node (frameworks and dependency
        # nodes) and the repository node. It needs a ``symbol`` node only when
        # that symbol is an endpoint of a relationship edge. Symbols dominate a
        # large snapshot, so excluding the unreferenced ones is the bound that
        # matters here — while still returning every node the consumer reads.
        endpoint_keys = {key for edge in edges for key in (edge.subject_key, edge.object_key)}
        node_filter = RiNode.node_kind.in_(ARCHITECTURE_NODE_KINDS)
        if endpoint_keys:
            node_filter = or_(node_filter, RiNode.stable_key.in_(endpoint_keys))
        nodes = list(
            self.db.scalars(
                select(RiNode)
                .where(RiNode.snapshot_id == snapshot.snapshot_id, node_filter)
                .order_by(RiNode.stable_key, RiNode.id)
            ).all()
        )
        diagnostics = list(
            self.db.scalars(
                select(RiDiagnostic)
                .where(
                    RiDiagnostic.snapshot_id == snapshot.snapshot_id,
                    RiDiagnostic.code.in_(ARCHITECTURE_FACT_DIAGNOSTIC_CODES),
                )
                .order_by(
                    RiDiagnostic.path,
                    RiDiagnostic.span_start_line,
                    RiDiagnostic.code,
                    RiDiagnostic.id,
                )
            ).all()
        )
        assertions = list(
            self.db.scalars(
                select(RiAssertion)
                .where(
                    RiAssertion.snapshot_id == snapshot.snapshot_id,
                    RiAssertion.predicate.in_(ARCHITECTURE_ASSERTION_PREDICATES),
                )
                .order_by(RiAssertion.subject_key, RiAssertion.predicate, RiAssertion.assertion_id, RiAssertion.id)
            ).all()
        )
        covered_paths = self._architecture_covered_paths(snapshot)
        return ArchitectureSnapshotFacts(
            snapshot=snapshot,
            nodes=nodes,
            edges=edges,
            assertions=assertions,
            node_evidence=self._evidence_for(snapshot, "node_ref", [node.id for node in nodes]),
            edge_evidence=self._evidence_for(snapshot, "edge_ref", [edge.id for edge in edges]),
            diagnostics=diagnostics,
            covered_paths=covered_paths,
        )

    def product_projection(self, repository_id: str) -> ProductSnapshotProjection:
        """Facts used by product documentation and free-form AI.

        Resolution is deliberately current-revision-only. The query reads only
        file/dependency nodes, file role assertions, route observations and
        diagnostics. Growing id sets are batched before entering ``IN`` clauses.
        """

        snapshot = self.require_sealed_snapshot_for_current_revision(repository_id)
        nodes = list(
            self.db.scalars(
                select(RiNode)
                .where(
                    RiNode.snapshot_id == snapshot.snapshot_id,
                    RiNode.node_kind.in_(("file", "dependency")),
                )
                .order_by(RiNode.node_kind, RiNode.stable_key, RiNode.id)
            ).all()
        )
        assertions = list(
            self.db.scalars(
                select(RiAssertion)
                .where(
                    RiAssertion.snapshot_id == snapshot.snapshot_id,
                    RiAssertion.subject_kind == "file",
                    RiAssertion.predicate == "classified_as",
                )
                .order_by(RiAssertion.subject_key, RiAssertion.assertion_id, RiAssertion.id)
            ).all()
        )
        roles: dict[str, tuple[str, str | None]] = {}
        for assertion in assertions:
            value = assertion.value or {}
            classification = value.get("classification")
            if isinstance(classification, str) and classification:
                confidence = value.get("confidence")
                roles[assertion.subject_key] = (
                    classification,
                    confidence if isinstance(confidence, str) else None,
                )

        files = tuple(
            SnapshotFileFact(
                path=node.stable_key.removeprefix("file:"),
                language=node.language,
                role=roles.get(node.stable_key, (None, None))[0],
                role_confidence=roles.get(node.stable_key, (None, None))[1],
            )
            for node in nodes
            if node.node_kind == "file" and node.stable_key.startswith("file:")
        )
        dependencies = tuple(
            self._project_dependency(node)
            for node in nodes
            if node.node_kind == "dependency"
        )
        language_counts = Counter(file.language for file in files if file.language)
        primary_language = (
            {"python": "Python", "typescript": "TypeScript"}.get(
                language_counts.most_common(1)[0][0],
                language_counts.most_common(1)[0][0].title(),
            )
            if language_counts
            else "Unknown"
        )
        framework_by_dependency = {
            "react": "React",
            "next": "Next.js",
            "vue": "Vue",
            "fastapi": "FastAPI",
            "django": "Django",
            "flask": "Flask",
        }
        dependency_names = {item.name.lower() for item in dependencies}
        frameworks = tuple(
            sorted(
                framework
                for name, framework in framework_by_dependency.items()
                if name in dependency_names
            )
        )
        entry_points = tuple(sorted(file.path for file in files if file.role == "entrypoint"))
        modules = self._project_modules(files)

        route_observations = list(
            self.db.scalars(
                select(RiObservation)
                .where(
                    RiObservation.snapshot_id == snapshot.snapshot_id,
                    RiObservation.observed_kind == "route",
                )
                .order_by(
                    RiObservation.subject_key,
                    RiObservation.referent_text,
                    RiObservation.observation_id,
                    RiObservation.id,
                )
            ).all()
        )
        route_evidence = self._evidence_for(
            snapshot,
            "observation_ref",
            [observation.id for observation in route_observations],
        )
        routes = tuple(
            SnapshotRouteFact(
                path=observation.referent_text or "Not available",
                evidence_paths=tuple(
                    sorted({item.path for item in route_evidence.get(observation.id, [])})
                ),
            )
            for observation in route_observations
        )
        diagnostics = tuple(
            (row.code, row.message, row.path)
            for row in self.db.scalars(
                select(RiDiagnostic)
                .where(RiDiagnostic.snapshot_id == snapshot.snapshot_id)
                .order_by(
                    RiDiagnostic.path,
                    RiDiagnostic.span_start_line,
                    RiDiagnostic.code,
                    RiDiagnostic.id,
                )
            ).all()
        )
        return ProductSnapshotProjection(
            snapshot_id=snapshot.snapshot_id,
            schema_version=snapshot.schema_version,
            repository_id=snapshot.repository_id,
            revision_kind=snapshot.revision_kind,
            revision_value=snapshot.revision_value,
            revision_ref=snapshot.revision_ref,
            canonical_graph_hash=snapshot.canonical_graph_hash or "",
            primary_language=primary_language,
            frameworks=frameworks,
            entry_points=entry_points,
            modules=modules,
            files=files,
            dependencies=dependencies,
            routes=routes,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _project_modules(files: tuple[SnapshotFileFact, ...]) -> tuple[SnapshotModuleFact, ...]:
        grouped: dict[str, list[SnapshotFileFact]] = defaultdict(list)
        for file in files:
            parts = [part for part in file.path.strip("/").split("/") if part]
            if file.role in {"controller", "route"}:
                key = "api"
            elif file.role in {"service", "repository", "middleware", "configuration", "test", "documentation"}:
                key = file.role
            elif file.role in {"model", "dto", "interface", "enum"}:
                key = "domain"
            elif parts and parts[0] in {"app", "src", "backend", "frontend", "apps"} and len(parts) > 1:
                key = parts[1].lower()
            else:
                key = parts[0].lower() if parts else "repository"
            grouped[key].append(file)
        result: list[SnapshotModuleFact] = []
        for key, members in sorted(grouped.items()):
            meaningful_roles = [
                item.role
                for item in members
                if item.role not in (None, "unknown", "documentation", "test")
            ]
            role = (
                Counter(meaningful_roles).most_common(1)[0][0]
                if meaningful_roles
                else (members[0].role or "unknown")
            )
            result.append(
                SnapshotModuleFact(
                    name=key.replace("-", " ").title(),
                    role=role,
                    paths=tuple(sorted(item.path for item in members)),
                )
            )
        return tuple(result)

    @staticmethod
    def _project_dependency(node: RiNode) -> SnapshotDependencyFact:
        properties: dict[str, Any] = node.properties or {}
        raw_declarations = properties.get("declarations")
        if not isinstance(raw_declarations, list):
            raw_declarations = [properties]
        declarations: list[SnapshotDependencyDeclaration] = []
        for raw in raw_declarations:
            if not isinstance(raw, dict):
                continue
            declarations.append(
                SnapshotDependencyDeclaration(
                    version=raw.get("version") if isinstance(raw.get("version"), str) else None,
                    dependency_type=raw.get("dependency_type") if isinstance(raw.get("dependency_type"), str) else None,
                    manifest_path=raw.get("manifest_path") if isinstance(raw.get("manifest_path"), str) else None,
                    workspace_path=raw.get("workspace_path") if isinstance(raw.get("workspace_path"), str) else None,
                    start_line=raw.get("start_line") if isinstance(raw.get("start_line"), int) else None,
                    end_line=raw.get("end_line") if isinstance(raw.get("end_line"), int) else None,
                    extractor=raw.get("extractor") if isinstance(raw.get("extractor"), str) else None,
                    extractor_version=raw.get("extractor_version") if isinstance(raw.get("extractor_version"), str) else None,
                )
            )
        return SnapshotDependencyFact(
            stable_key=node.stable_key,
            name=node.name or node.stable_key,
            ecosystem=properties.get("ecosystem") if isinstance(properties.get("ecosystem"), str) else None,
            declarations=tuple(declarations),
        )

    def symbols(self, snapshot_id: str, *, offset: int, limit: int) -> tuple[RiSnapshot, list[RiNode], int]:
        snapshot = self._snapshot(snapshot_id)
        where = (RiNode.snapshot_id == snapshot.snapshot_id, RiNode.node_kind == "symbol")
        rows, total = self._page(RiNode, where, (RiNode.stable_key, RiNode.id), offset, limit)
        return snapshot, rows, total

    def neighbours(
        self, snapshot_id: str, *, node_key: str, offset: int, limit: int
    ) -> tuple[RiSnapshot, list[RiEdge], int]:
        snapshot = self._snapshot(snapshot_id)
        where = (
            RiEdge.snapshot_id == snapshot.snapshot_id,
            or_(RiEdge.subject_key == node_key, RiEdge.object_key == node_key),
        )
        rows, total = self._page(
            RiEdge,
            where,
            (RiEdge.subject_key, RiEdge.predicate, RiEdge.object_key, RiEdge.edge_id, RiEdge.id),
            offset,
            limit,
        )
        return snapshot, rows, total

    def references(self, snapshot_id: str, *, offset: int, limit: int) -> tuple[RiSnapshot, list[RiEdge], int]:
        """Return only stored resolved relationship facts, never unresolved observations."""

        snapshot = self._snapshot(snapshot_id)
        where = (RiEdge.snapshot_id == snapshot.snapshot_id,)
        rows, total = self._page(
            RiEdge,
            where,
            (RiEdge.subject_key, RiEdge.predicate, RiEdge.object_key, RiEdge.edge_id, RiEdge.id),
            offset,
            limit,
        )
        return snapshot, rows, total

    def assertions(self, snapshot_id: str, *, offset: int, limit: int) -> tuple[RiSnapshot, list[RiAssertion], int]:
        snapshot = self._snapshot(snapshot_id)
        rows, total = self._page(
            RiAssertion,
            (RiAssertion.snapshot_id == snapshot.snapshot_id,),
            (RiAssertion.subject_key, RiAssertion.predicate, RiAssertion.assertion_id, RiAssertion.id),
            offset,
            limit,
        )
        return snapshot, rows, total

    def paths(self, snapshot_id: str, *, offset: int, limit: int) -> tuple[RiSnapshot, list[RiNode], int]:
        snapshot = self._snapshot(snapshot_id)
        where = (RiNode.snapshot_id == snapshot.snapshot_id, RiNode.node_kind == "file")
        rows, total = self._page(RiNode, where, (RiNode.stable_key, RiNode.id), offset, limit)
        return snapshot, rows, total

    def evidence(self, snapshot_id: str, *, offset: int, limit: int) -> tuple[RiSnapshot, list[RiEvidence], int]:
        snapshot = self._snapshot(snapshot_id)
        where = (RiEvidence.snapshot_id == snapshot.snapshot_id,)
        rows, total = self._page(
            RiEvidence,
            where,
            (
                RiEvidence.path,
                RiEvidence.start_line,
                RiEvidence.end_line,
                RiEvidence.granularity,
                RiEvidence.extractor,
                RiEvidence.extractor_version,
                RiEvidence.id,
            ),
            offset,
            limit,
        )
        return snapshot, rows, total

    def evidence_for_nodes(self, snapshot: RiSnapshot, nodes: list[RiNode]) -> dict[int, list[RiEvidence]]:
        return self._evidence_for(snapshot, "node_ref", [node.id for node in nodes])

    def evidence_for_edges(self, snapshot: RiSnapshot, edges: list[RiEdge]) -> dict[int, list[RiEvidence]]:
        return self._evidence_for(snapshot, "edge_ref", [edge.id for edge in edges])

    def derivations_for_edges(self, snapshot: RiSnapshot, edges: list[RiEdge]) -> dict[int, list[RiDerivation]]:
        if not edges:
            return {}
        rows = self.db.scalars(
            select(RiDerivation)
            .where(RiDerivation.snapshot_id == snapshot.snapshot_id, RiDerivation.edge_ref.in_([edge.id for edge in edges]))
            .order_by(RiDerivation.ref_kind, RiDerivation.ref_identity, RiDerivation.id)
        ).all()
        grouped: dict[int, list[RiDerivation]] = defaultdict(list)
        for row in rows:
            if row.edge_ref is not None:
                grouped[row.edge_ref].append(row)
        return grouped

    def derivations_for_assertions(self, snapshot: RiSnapshot, assertions: list[RiAssertion]) -> dict[int, list[RiDerivation]]:
        if not assertions:
            return {}
        rows = self.db.scalars(
            select(RiDerivation)
            .where(
                RiDerivation.snapshot_id == snapshot.snapshot_id,
                RiDerivation.assertion_ref.in_([assertion.id for assertion in assertions]),
            )
            .order_by(RiDerivation.ref_kind, RiDerivation.ref_identity, RiDerivation.id)
        ).all()
        grouped: dict[int, list[RiDerivation]] = defaultdict(list)
        for row in rows:
            if row.assertion_ref is not None:
                grouped[row.assertion_ref].append(row)
        return grouped

    def fact_identity_for_evidence(self, snapshot: RiSnapshot, evidence: list[RiEvidence]) -> dict[tuple[str, int], str]:
        node_refs = [item.node_ref for item in evidence if item.node_ref is not None]
        edge_refs = [item.edge_ref for item in evidence if item.edge_ref is not None]
        observation_refs = [item.observation_ref for item in evidence if item.observation_ref is not None]
        identities: dict[tuple[str, int], str] = {}
        if node_refs:
            for node in self.db.scalars(select(RiNode).where(RiNode.snapshot_id == snapshot.snapshot_id, RiNode.id.in_(node_refs))):
                identities[("node", node.id)] = node.stable_key
        if edge_refs:
            for edge in self.db.scalars(select(RiEdge).where(RiEdge.snapshot_id == snapshot.snapshot_id, RiEdge.id.in_(edge_refs))):
                identities[("edge", edge.id)] = edge.edge_id
        if observation_refs:
            from app.models.snapshot import RiObservation

            for observation in self.db.scalars(
                select(RiObservation).where(RiObservation.snapshot_id == snapshot.snapshot_id, RiObservation.id.in_(observation_refs))
            ):
                identities[("observation", observation.id)] = observation.observation_id
        return identities

    def _snapshot(self, snapshot_id: str) -> RiSnapshot:
        from app.models.repository import RepositoryRecord

        snapshot = self.db.scalars(
            select(RiSnapshot)
            .join(RepositoryRecord, RepositoryRecord.id == RiSnapshot.repository_id)
            .where(
                RiSnapshot.snapshot_id == snapshot_id,
                RiSnapshot.state == "completed",
                RepositoryRecord.owner_id == self.owner_id,
            )
        ).first()
        if snapshot is None:
            raise NotFoundError("Snapshot not found.")
        if snapshot.schema_version not in self.supported_schema_versions:
            raise UnsupportedSchemaVersionError(
                f"Unsupported snapshot schema version: {snapshot.schema_version}.",
                details={"received": snapshot.schema_version, "supported": list(self.supported_schema_versions)},
            )
        return snapshot

    def _latest_snapshot(self, repository_id: str) -> RiSnapshot | None:
        from app.models.repository import RepositoryRecord

        snapshot = self.db.scalars(
            select(RiSnapshot)
            .join(RepositoryRecord, RepositoryRecord.id == RiSnapshot.repository_id)
            .where(
                RiSnapshot.repository_id == repository_id,
                RiSnapshot.state == "completed",
                RepositoryRecord.owner_id == self.owner_id,
            )
            .order_by(RiSnapshot.sealed_at.desc(), RiSnapshot.snapshot_id)
        ).first()
        if snapshot is not None and snapshot.schema_version not in self.supported_schema_versions:
            raise UnsupportedSchemaVersionError(
                f"Unsupported snapshot schema version: {snapshot.schema_version}.",
                details={"received": snapshot.schema_version, "supported": list(self.supported_schema_versions)},
            )
        return snapshot

    def _page(self, model, where: tuple, order_by: tuple, offset: int, limit: int):
        total = self.db.scalar(select(func.count()).select_from(model).where(*where)) or 0
        rows = self.db.scalars(select(model).where(*where).order_by(*order_by).offset(offset).limit(limit)).all()
        return list(rows), total

    def _architecture_covered_paths(self, snapshot: RiSnapshot) -> set[str]:
        """Return snapshot paths that carry non-inventory extraction evidence.

        Inventory-only file evidence proves a path exists, not that a
        relationship-capable extractor ran over it, so the architecture consumer
        uses this set to avoid reporting an unsupported file as genuinely
        isolated.

        The result is one distinct-path column read rather than a full evidence
        materialization: previously the caller derived these paths by walking
        every node and observation evidence row it had already loaded, which is
        what made the read unbounded on large snapshots (#133).
        """

        return set(
            self.db.scalars(
                select(RiEvidence.path)
                .where(
                    RiEvidence.snapshot_id == snapshot.snapshot_id,
                    RiEvidence.extractor != "repository-inventory",
                    or_(RiEvidence.node_ref.is_not(None), RiEvidence.observation_ref.is_not(None)),
                )
                .distinct()
            ).all()
        )

    def _evidence_for(self, snapshot: RiSnapshot, column: str, ids: list[int]) -> dict[int, list[RiEvidence]]:
        if not ids:
            return {}
        field = getattr(RiEvidence, column)
        grouped: dict[int, list[RiEvidence]] = defaultdict(list)
        for start in range(0, len(ids), ARCHITECTURE_EVIDENCE_BATCH_SIZE):
            rows = self.db.scalars(
                select(RiEvidence)
                .where(
                    RiEvidence.snapshot_id == snapshot.snapshot_id,
                    field.in_(ids[start : start + ARCHITECTURE_EVIDENCE_BATCH_SIZE]),
                )
                .order_by(
                    RiEvidence.path,
                    RiEvidence.start_line,
                    RiEvidence.end_line,
                    RiEvidence.granularity,
                    RiEvidence.extractor,
                    RiEvidence.extractor_version,
                    RiEvidence.id,
                )
            ).all()
            for row in rows:
                parent = getattr(row, column)
                if parent is not None:
                    grouped[parent].append(row)
        return grouped
