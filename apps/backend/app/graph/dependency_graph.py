"""Dependency Graph read model, built exclusively from a sealed ri.v1 snapshot (#158).

No filesystem read, no working-tree fallback, and no legacy
``repo_metadata['intelligence']`` read: every field is derived from
:class:`SnapshotQueryService` facts. A repository with no sealed snapshot for
its current revision raises ``NotFoundError`` (via
``require_sealed_snapshot_for_current_revision``) — the same 404 contract
Architecture, Review, and Insights already use, with no legacy fallback.
"""

from __future__ import annotations

import posixpath

from sqlalchemy import select

from app.analysis.manifest import build_manifest, manifest_digest
from app.intelligence.query_service import SnapshotQueryService
from app.extraction.support_matrix import supported_manifest_filenames
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiDiagnostic, RiEdge, RiEvidence, RiNode
from app.schemas.dependencies import (
    DependencyAssessment,
    DependencyDeclaration,
    DependencyDiagnostic,
    DependencyEdge,
    DependencyGraphResponse,
    DependencyNode,
    DependencyProvenance,
)

#: Manifest filenames ``DependencyManifestExtractor`` supports (app/extraction/manifests.py).
#: A diagnostic is "relevant to dependency extraction" only when it names one of these paths —
#: the same scoping the legacy engine got for free by only ever iterating manifest-supporting files.
_MANIFEST_FILENAMES = frozenset(supported_manifest_filenames())
#: Codes the manifest extractor and the pipeline's size-budget gate can emit for a manifest file.
_RELEVANT_DIAGNOSTIC_CODES = frozenset({"RI-SRC-MALFORMED", "RI-LIMIT-SKIP"})


class DependencyGraphBuilder:
    """Build the Dependency Graph response solely from an owner-scoped sealed snapshot."""

    def __init__(self, snapshots: SnapshotQueryService) -> None:
        self.snapshots = snapshots

    def build(self, record: RepositoryRecord) -> DependencyGraphResponse:
        snapshot = self.snapshots.require_sealed_snapshot_for_current_revision(record.id)

        dependency_nodes = [
            item
            for item in self.snapshots.db.scalars(
                select(RiNode)
                .where(RiNode.snapshot_id == snapshot.snapshot_id, RiNode.node_kind == "dependency")
                .order_by(RiNode.stable_key, RiNode.id)
            )
            if self._is_declared(item)
        ]
        node_evidence = self.snapshots.evidence_for_nodes(snapshot, dependency_nodes)
        nodes = [self._node(item, node_evidence.get(item.id, [])) for item in dependency_nodes]
        dependency_keys = {item.stable_key for item in dependency_nodes}

        depends_on_edges = list(
            self.snapshots.db.scalars(
                select(RiEdge)
                .where(RiEdge.snapshot_id == snapshot.snapshot_id, RiEdge.predicate == "depends_on")
                .order_by(RiEdge.subject_key, RiEdge.object_key, RiEdge.edge_id, RiEdge.id)
            )
        )
        edges = [
            DependencyEdge(id=edge.edge_id, source=edge.subject_key, target=edge.object_key, type="depends-on")
            for edge in depends_on_edges
            if edge.object_key in dependency_keys
        ]

        diagnostics = [
            item
            for item in self.snapshots.db.scalars(
                select(RiDiagnostic)
                .where(
                    RiDiagnostic.snapshot_id == snapshot.snapshot_id, RiDiagnostic.code.in_(_RELEVANT_DIAGNOSTIC_CODES)
                )
                .order_by(RiDiagnostic.path, RiDiagnostic.code, RiDiagnostic.id)
            )
            if item.path and posixpath.basename(item.path) in _MANIFEST_FILENAMES
        ]

        manifest_paths = {declaration.manifest_path for node in nodes for declaration in node.declarations}
        manifest_paths.update(item.path for item in diagnostics if item.path)

        manifest = build_manifest(snapshot)
        return DependencyGraphResponse(
            repository_id=record.id,
            repository_name=record.name,
            revision_kind=snapshot.revision_kind,  # type: ignore[arg-type]
            revision_value=snapshot.revision_value,
            snapshot_id=snapshot.snapshot_id,
            snapshot_schema_version=snapshot.schema_version,
            canonical_graph_hash=snapshot.canonical_graph_hash,
            manifest_digest=manifest_digest(manifest),
            provenance=DependencyProvenance(
                snapshot_id=snapshot.snapshot_id,
                snapshot_schema_version=snapshot.schema_version,
                canonical_graph_hash=snapshot.canonical_graph_hash,
            ),
            generated_at=snapshot.sealed_at,
            nodes=nodes,
            edges=edges,
            total_dependencies=len(nodes),
            manifest_count=len(manifest_paths),
            diagnostics=[
                DependencyDiagnostic(
                    code=item.code,
                    category=item.category,
                    severity=item.severity,  # type: ignore[arg-type]
                    message=item.message,
                    path=item.path,
                    producer=item.producer,
                    details=dict(item.details) if item.details is not None else None,
                )
                for item in diagnostics
            ],
            vulnerability_assessment=DependencyAssessment(status="not_computed"),
            outdated_assessment=DependencyAssessment(status="not_computed"),
        )

    @staticmethod
    def _is_declared(item: RiNode) -> bool:
        """Keep only dependencies a manifest actually declares.

        Since #209 a ``dependency`` node can exist purely because a lockfile
        pinned it, which is every transitive package in a real ``package-lock``.
        This response is the *direct* dependency graph, so rendering one would
        claim the repository depends on a package it never asked for — and it
        would arrive with no version and a ``multiple`` type, because it has no
        declarations to summarize. A pre-#156 snapshot stored its single
        declaration flat on the node, so that shape counts as declared too.
        """

        properties = item.properties or {}
        declarations = properties.get("declarations")
        if declarations is None:
            return bool(properties.get("manifest_path"))
        return bool(declarations)

    @staticmethod
    def _node(item: RiNode, evidence: list[RiEvidence]) -> DependencyNode:
        properties = item.properties or {}
        ecosystem = str(properties.get("ecosystem") or "")
        raw_declarations = properties.get("declarations")
        if raw_declarations is None:
            # A node sealed before #156 stored one flat declaration directly on
            # the node's own properties, with the node's own evidence entry
            # carrying its line span and extractor identity. Sealed snapshots
            # are immutable, so a pre-fix snapshot can still be read this way
            # rather than raising on an older, still-valid shape.
            first_evidence = evidence[0] if evidence else None
            raw_declarations = (
                [
                    {
                        "name": item.name,
                        "version": properties.get("version"),
                        "dependency_type": properties.get("dependency_type"),
                        "manifest_path": properties.get("manifest_path"),
                        "workspace_path": properties.get("workspace_path"),
                        "start_line": first_evidence.start_line if first_evidence else 1,
                        "end_line": first_evidence.end_line if first_evidence else 1,
                        "extractor": first_evidence.extractor if first_evidence else "",
                        "extractor_version": first_evidence.extractor_version if first_evidence else "",
                    }
                ]
                if properties.get("manifest_path")
                else []
            )
        declarations = sorted(
            (
                DependencyDeclaration(
                    name=str(declaration.get("name") or item.name or ""),
                    manifest_path=str(declaration.get("manifest_path") or ""),
                    workspace_path=str(declaration.get("workspace_path") or ""),
                    start_line=int(declaration.get("start_line") or 1),
                    end_line=int(declaration.get("end_line") or 1),
                    extractor=str(declaration.get("extractor") or ""),
                    extractor_version=str(declaration.get("extractor_version") or ""),
                    ecosystem=ecosystem,
                    version=declaration.get("version"),
                    type=declaration.get("dependency_type"),  # type: ignore[arg-type]
                )
                for declaration in raw_declarations
            ),
            key=lambda declaration: (declaration.manifest_path, declaration.start_line, declaration.end_line),
        )
        versions = {declaration.version for declaration in declarations}
        types = {declaration.type for declaration in declarations}
        return DependencyNode(
            id=item.stable_key,
            name=item.name or item.stable_key,
            version=next(iter(versions)) if len(versions) == 1 else None,
            type=next(iter(types)) if len(types) == 1 else "multiple",
            ecosystem=ecosystem,
            declarations=declarations,
        )
