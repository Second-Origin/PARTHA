"""Deterministic repository metrics over one sealed ``ri.v1`` snapshot."""

from __future__ import annotations

from sqlalchemy import func, select

from app.analysis.manifest import build_manifest, manifest_digest
from app.core.exceptions import NotFoundError
from app.intelligence.query_service import SnapshotQueryService
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiDiagnostic, RiEdge, RiEvidence, RiNode
from app.schemas.insights import (
    InsightBreakdown,
    InsightExtractor,
    InsightMetric,
    InsightProvenance,
    RepositoryInsightsResponse,
)


def _producer_parts(producer: str) -> tuple[str, str]:
    name, separator, version = producer.rpartition("@")
    return (name, version) if separator else (producer, "")


class RepositoryInsightsBuilder:
    """Compute only metrics whose definitions are exact and snapshot-local."""

    def __init__(self, snapshots: SnapshotQueryService) -> None:
        self.snapshots = snapshots

    def build(self, record: RepositoryRecord) -> RepositoryInsightsResponse:
        snapshot = self.snapshots.latest_snapshot_for_owner(record.id)
        if snapshot is None:
            raise NotFoundError(
                "No sealed Repository Intelligence snapshot is available for this repository.",
                {"repositoryId": record.id},
            )
        if (
            snapshot.repository_id != record.id
            or snapshot.revision_kind != record.revision_kind
            or snapshot.revision_value != record.revision_value
        ):
            raise NotFoundError(
                "The sealed snapshot does not match the selected repository revision.",
                {"repositoryId": record.id, "snapshotId": snapshot.snapshot_id},
            )
        if snapshot.canonical_graph_hash is None or snapshot.sealed_at is None:
            raise NotFoundError(
                "The selected repository revision has no sealed snapshot.",
                {"repositoryId": record.id},
            )

        snapshot_id = snapshot.snapshot_id
        provenance = InsightProvenance(
            snapshot_id=snapshot_id,
            snapshot_schema_version=snapshot.schema_version,
            canonical_graph_hash=snapshot.canonical_graph_hash,
        )

        node_counts = {
            kind: count
            for kind, count in self.snapshots.db.execute(
                select(RiNode.node_kind, func.count(RiNode.id))
                .where(RiNode.snapshot_id == snapshot_id)
                .group_by(RiNode.node_kind)
            ).all()
        }
        relationship_counts = {
            predicate: count
            for predicate, count in self.snapshots.db.execute(
                select(RiEdge.predicate, func.count(RiEdge.id))
                .where(RiEdge.snapshot_id == snapshot_id)
                .group_by(RiEdge.predicate)
            ).all()
        }
        diagnostic_severity_counts = {
            severity: count
            for severity, count in self.snapshots.db.execute(
                select(RiDiagnostic.severity, func.count(RiDiagnostic.id))
                .where(RiDiagnostic.snapshot_id == snapshot_id)
                .group_by(RiDiagnostic.severity)
            ).all()
        }
        diagnostic_code_counts = {
            code: count
            for code, count in self.snapshots.db.execute(
                select(RiDiagnostic.code, func.count(RiDiagnostic.id))
                .where(RiDiagnostic.snapshot_id == snapshot_id)
                .group_by(RiDiagnostic.code)
            ).all()
        }
        language_counts = {
            language: count
            for language, count in self.snapshots.db.execute(
                select(RiNode.language, func.count(RiNode.id))
                .where(
                    RiNode.snapshot_id == snapshot_id,
                    RiNode.node_kind == "file",
                    RiNode.language.is_not(None),
                )
                .group_by(RiNode.language)
            ).all()
            if language is not None
        }
        evidence_count = (
            self.snapshots.db.scalar(
                select(func.count(RiEvidence.id)).where(RiEvidence.snapshot_id == snapshot_id)
            )
            or 0
        )
        evidence_extractor_counts = {
            (name, version): count
            for name, version, count in self.snapshots.db.execute(
                select(
                    RiEvidence.extractor,
                    RiEvidence.extractor_version,
                    func.count(RiEvidence.id),
                )
                .where(RiEvidence.snapshot_id == snapshot_id)
                .group_by(RiEvidence.extractor, RiEvidence.extractor_version)
            ).all()
        }

        eligible_files = {
            node.stable_key.removeprefix("file:")
            for node in self.snapshots.db.scalars(
                select(RiNode).where(
                    RiNode.snapshot_id == snapshot_id,
                    RiNode.node_kind == "file",
                    RiNode.language.is_not(None),
                )
            ).all()
        }
        semantic_paths = set(
            self.snapshots.db.scalars(
                select(RiEvidence.path)
                .where(
                    RiEvidence.snapshot_id == snapshot_id,
                    RiEvidence.extractor != "repository-inventory",
                )
                .distinct()
            ).all()
        )
        covered_files = len(eligible_files & semantic_paths)
        eligible_count = len(eligible_files)

        def metric(
            metric_id: str,
            label: str,
            value: int | float | str | None,
            unit: str,
            definition: str,
            *,
            state: str = "assessed",
            numerator: int | None = None,
            denominator: int | None = None,
        ) -> InsightMetric:
            return InsightMetric(
                id=metric_id,
                label=label,
                value=value,
                unit=unit,
                definition=definition,
                provenance=provenance,
                assessment_state=state,  # type: ignore[arg-type]
                snapshot_id=snapshot_id,
                numerator=numerator,
                denominator=denominator,
            )

        metrics = [
            metric(
                "nodes.files.total",
                "File nodes",
                node_counts.get("file", 0),
                "nodes",
                "Count of observed ri.v1 nodes whose node kind is file.",
            ),
            metric(
                "nodes.symbols.total",
                "Symbol nodes",
                node_counts.get("symbol", 0),
                "nodes",
                "Count of observed ri.v1 nodes whose node kind is symbol.",
            ),
            metric(
                "nodes.dependencies.total",
                "Dependency nodes",
                node_counts.get("dependency", 0),
                "nodes",
                "Count of observed ri.v1 nodes whose node kind is dependency.",
            ),
            metric(
                "relationships.resolved.total",
                "Resolved relationships",
                sum(relationship_counts.values()),
                "relationships",
                "Count of sealed ri.v1 edges. Every stored edge has resolved truth class.",
            ),
            metric(
                "evidence.records.total",
                "Evidence records",
                evidence_count,
                "records",
                "Count of stored source evidence records in the selected snapshot.",
            ),
            metric(
                "diagnostics.relationships.unresolved",
                "Unresolved relationships",
                diagnostic_code_counts.get("RI-RES-UNRESOLVED", 0),
                "diagnostics",
                "Count of sealed diagnostics with code RI-RES-UNRESOLVED.",
            ),
            metric(
                "diagnostics.relationships.ambiguous",
                "Ambiguous relationships",
                diagnostic_code_counts.get("RI-RES-AMBIGUOUS", 0),
                "diagnostics",
                "Count of sealed diagnostics with code RI-RES-AMBIGUOUS.",
            ),
            metric(
                "diagnostics.source.unsupported",
                "Unsupported source constructs",
                diagnostic_code_counts.get("RI-EXT-UNSUPPORTED", 0),
                "diagnostics",
                "Count of sealed diagnostics with code RI-EXT-UNSUPPORTED.",
            ),
            metric(
                "diagnostics.source.malformed",
                "Malformed source files",
                diagnostic_code_counts.get("RI-SRC-MALFORMED", 0),
                "diagnostics",
                "Count of sealed diagnostics with code RI-SRC-MALFORMED.",
            ),
            metric(
                "extraction.files.semantic",
                "Files with semantic extraction evidence",
                covered_files,
                "files",
                "Eligible file paths with at least one evidence record from an extractor other than repository-inventory.",
            ),
            metric(
                "extraction.files.eligible",
                "Eligible files",
                eligible_count,
                "files",
                "Observed file nodes whose stored language is supported by a semantic extractor.",
            ),
            metric(
                "extraction.coverage",
                "Semantic extraction coverage",
                covered_files / eligible_count if eligible_count else None,
                "ratio",
                "Files with semantic extraction evidence divided by total eligible files.",
                state="assessed" if eligible_count else "insufficient_evidence",
                numerator=covered_files,
                denominator=eligible_count,
            ),
            metric(
                "assessment.vulnerability-scanning",
                "Vulnerability scanning",
                None,
                "status",
                "No vulnerability scanner contributes facts to repository-insights.v1.",
                state="not_assessed",
            ),
        ]

        producer_set = [_producer_parts(str(item)) for item in snapshot.producer_version_set or []]
        # Include an evidence extractor even if a legacy snapshot omitted it
        # from producer_version_set; this is still observed provenance, not an
        # invented producer.  Deterministic sorting keeps responses stable.
        all_extractors = sorted(set(producer_set) | set(evidence_extractor_counts))
        extractors = [
            InsightExtractor(
                name=name,
                version=version,
                evidence_record_count=evidence_extractor_counts.get((name, version), 0),
            )
            for name, version in all_extractors
        ]

        manifest = build_manifest(snapshot)
        return RepositoryInsightsResponse(
            repository_id=record.id,
            repository_name=record.name,
            revision_kind=snapshot.revision_kind,  # type: ignore[arg-type]
            revision_value=snapshot.revision_value,
            snapshot_id=snapshot_id,
            snapshot_schema_version=snapshot.schema_version,
            canonical_graph_hash=snapshot.canonical_graph_hash,
            manifest_digest=manifest_digest(manifest),
            provenance=provenance,
            # A deterministic computation over immutable facts is valid as of
            # sealing time; using wall-clock time would make identical reads
            # needlessly differ.
            computed_at=snapshot.sealed_at,
            snapshot_created_at=snapshot.created_at,
            snapshot_sealed_at=snapshot.sealed_at,
            extractor_set=extractors,
            metrics=metrics,
            relationships_by_predicate=[
                InsightBreakdown(key=key, label=key.replace("_", " "), value=value)
                for key, value in sorted(relationship_counts.items())
            ],
            diagnostics_by_severity=[
                InsightBreakdown(key=key, label=key, value=value)
                for key, value in sorted(diagnostic_severity_counts.items())
            ],
            diagnostics_by_code=[
                InsightBreakdown(key=key, label=key, value=value)
                for key, value in sorted(diagnostic_code_counts.items())
            ],
            languages=[
                InsightBreakdown(key=key, label=key, value=value)
                for key, value in sorted(language_counts.items())
            ],
        )
