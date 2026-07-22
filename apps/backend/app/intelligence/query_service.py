"""Read-only, owner-scoped queries over sealed ``ri.v1`` snapshots (#92)."""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import func, or_, select
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


ARCHITECTURE_RELATIONSHIP_EDGE_TYPES = {
    "imports": "import",
    "calls": "calls",
    "routes_to": "api-call",
    "implements": "dependency",
    "depends_on": "dependency",
}
ARCHITECTURE_EVIDENCE_PATH_BATCH_SIZE = 500


@dataclass(frozen=True)
class ArchitectureSnapshotFacts:
    """Persisted facts needed to build evidence-backed architecture relationships."""

    snapshot: RiSnapshot
    nodes: list[RiNode]
    edges: list[RiEdge]
    node_evidence: dict[int, list[RiEvidence]]
    edge_evidence: dict[int, list[RiEvidence]]
    diagnostics: list[RiDiagnostic]
    covered_paths: set[str]


class SnapshotQueryService:
    """Expose only persisted snapshot facts; this service never touches repository storage."""

    def __init__(self, db: Session, owner_id: str) -> None:
        self.db = db
        self.owner_id = owner_id

    supported_schema_versions = ("ri.v1",)

    def metadata(self, snapshot_id: str) -> RiSnapshot:
        return self._snapshot(snapshot_id)

    def architecture_facts(
        self,
        repository_id: str,
        *,
        module_paths: Collection[str],
    ) -> ArchitectureSnapshotFacts | None:
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
                    RiEdge.predicate.in_(ARCHITECTURE_RELATIONSHIP_EDGE_TYPES),
                )
                .order_by(RiEdge.subject_key, RiEdge.predicate, RiEdge.object_key, RiEdge.edge_id, RiEdge.id)
            ).all()
        )
        endpoint_keys = {key for edge in edges for key in (edge.subject_key, edge.object_key)}
        nodes = (
            list(
                self.db.scalars(
                    select(RiNode)
                    .where(RiNode.snapshot_id == snapshot.snapshot_id, RiNode.stable_key.in_(endpoint_keys))
                    .order_by(RiNode.stable_key, RiNode.id)
                ).all()
            )
            if endpoint_keys
            else []
        )
        diagnostics = list(
            self.db.scalars(
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
        covered_paths = self._architecture_covered_paths(snapshot, module_paths)
        return ArchitectureSnapshotFacts(
            snapshot=snapshot,
            nodes=nodes,
            edges=edges,
            node_evidence=self._evidence_for(snapshot, "node_ref", [node.id for node in nodes]),
            edge_evidence=self._evidence_for(snapshot, "edge_ref", [edge.id for edge in edges]),
            diagnostics=diagnostics,
            covered_paths=covered_paths,
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

    def _architecture_covered_paths(self, snapshot: RiSnapshot, module_paths: Collection[str]) -> set[str]:
        """Return only module paths with non-inventory extraction evidence."""

        paths = sorted(set(module_paths))
        covered_paths: set[str] = set()
        for start in range(0, len(paths), ARCHITECTURE_EVIDENCE_PATH_BATCH_SIZE):
            covered_paths.update(
                self.db.scalars(
                    select(RiEvidence.path)
                    .where(
                        RiEvidence.snapshot_id == snapshot.snapshot_id,
                        RiEvidence.path.in_(paths[start : start + ARCHITECTURE_EVIDENCE_PATH_BATCH_SIZE]),
                        RiEvidence.extractor != "repository-inventory",
                        or_(RiEvidence.node_ref.is_not(None), RiEvidence.observation_ref.is_not(None)),
                    )
                    .distinct()
                ).all()
            )
        return covered_paths

    def _evidence_for(self, snapshot: RiSnapshot, column: str, ids: list[int]) -> dict[int, list[RiEvidence]]:
        if not ids:
            return {}
        field = getattr(RiEvidence, column)
        rows = self.db.scalars(
            select(RiEvidence)
            .where(RiEvidence.snapshot_id == snapshot.snapshot_id, field.in_(ids))
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
        grouped: dict[int, list[RiEvidence]] = defaultdict(list)
        for row in rows:
            parent = getattr(row, column)
            if parent is not None:
                grouped[parent].append(row)
        return grouped
