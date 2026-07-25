"""Deterministic, revision-bound Engineering Review generation (#154).

The legacy implementation subtracted arbitrary severity costs from 100 and
generated generic recommendations from mutable repository metadata.  This
builder deliberately has no dependency on ``RepositoryIntelligenceEngine``.
It emits only sealed ``ri.v1`` diagnostics that have an authentic supporting
evidence span in the same snapshot.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import or_, select

from app.analysis.manifest import build_manifest, manifest_digest
from app.core.exceptions import NotFoundError
from app.intelligence.canonical import canonical_json_bytes
from app.intelligence.query_service import SnapshotQueryService
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiDiagnostic, RiEvidence, RiNode, RiObservation
from app.schemas.review import (
    AssessmentState,
    EngineeringReviewResponse,
    ReviewCategoryAssessment,
    ReviewCategoryId,
    ReviewEvidenceReference,
    ReviewFinding,
    ReviewProvenance,
    ReviewSeverity,
    ReviewSeverityCounts,
    ReviewSummary,
)

# Stored extractor severity -> product finding severity.  This is the complete,
# documented mapping; no language model or score calculation is involved.
DIAGNOSTIC_SEVERITY_MAPPING: dict[str, ReviewSeverity] = {
    "fatal": "critical",
    "error": "high",
    "warning": "medium",
    "info": "info",
}

_RULES: dict[str, tuple[ReviewCategoryId, str, str]] = {
    "RI-RES-UNRESOLVED": (
        "relationship_resolution",
        "Unresolved relationship",
        "Inspect the referenced name at this source span and make its target explicit or add extractor support for the construct.",
    ),
    "RI-RES-AMBIGUOUS": (
        "relationship_resolution",
        "Ambiguous relationship",
        "Disambiguate the referenced name at this source span so it resolves to one target.",
    ),
    "RI-EXT-UNSUPPORTED": (
        "source_extraction",
        "Unsupported source construct",
        "Rewrite the recorded construct into a supported form or extend the named extractor before relying on it for repository relationships.",
    ),
    "RI-SRC-MALFORMED": (
        "source_extraction",
        "Malformed source",
        "Store this source as valid UTF-8 before attempting line-addressed semantic extraction.",
    ),
    "RI-LIMIT-SKIP": (
        "source_extraction",
        "Source excluded by extraction limit",
        "Reduce the file below the configured extraction limit or raise the documented limit and rerun analysis.",
    ),
}

_CATEGORY_LABELS: dict[ReviewCategoryId, str] = {
    "architecture_boundaries": "Architecture and boundaries",
    "relationship_resolution": "Relationship resolution",
    "source_extraction": "Source extraction",
    "dependency_declarations": "Dependency declarations",
    "security_vulnerability_scanning": "Security vulnerability scanning",
    "authentication_evidence": "Authentication evidence",
    "repository_structure": "Repository structure",
    "analysis_integrity": "Analysis integrity",
}


@dataclass(frozen=True)
class _SupportedEvidence:
    fact_id: str
    evidence: RiEvidence


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"{prefix}:{digest}"


class EngineeringReviewBuilder:
    """Build the public review solely from an owner-scoped sealed snapshot."""

    def __init__(self, snapshots: SnapshotQueryService) -> None:
        self.snapshots = snapshots

    def build(self, record: RepositoryRecord) -> EngineeringReviewResponse:
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
            # Fail closed even if persistence constraints are bypassed or a test
            # double supplies mismatched facts.
            raise NotFoundError(
                "The sealed snapshot does not match the selected repository revision.",
                {"repositoryId": record.id, "snapshotId": snapshot.snapshot_id},
            )
        if snapshot.canonical_graph_hash is None or snapshot.sealed_at is None:
            raise NotFoundError(
                "The selected repository revision has no sealed snapshot.",
                {"repositoryId": record.id},
            )

        diagnostics = list(
            self.snapshots.db.scalars(
                select(RiDiagnostic)
                .where(RiDiagnostic.snapshot_id == snapshot.snapshot_id)
                .order_by(
                    RiDiagnostic.code,
                    RiDiagnostic.path,
                    RiDiagnostic.span_start_line,
                    RiDiagnostic.span_end_line,
                    RiDiagnostic.producer,
                    RiDiagnostic.message,
                    RiDiagnostic.id,
                )
            ).all()
        )
        evidence_by_fact = self._evidence_by_fact(snapshot.snapshot_id, diagnostics)
        provenance = ReviewProvenance(
            snapshot_id=snapshot.snapshot_id,
            snapshot_schema_version=snapshot.schema_version,
            canonical_graph_hash=snapshot.canonical_graph_hash,
        )

        findings: list[ReviewFinding] = []
        omitted = 0
        for diagnostic in diagnostics:
            rule = _RULES.get(diagnostic.code)
            supported = self._support_for(diagnostic, evidence_by_fact)
            if rule is None or supported is None:
                omitted += 1
                continue
            category, title, remediation = rule
            evidence = supported.evidence
            evidence_id = _stable_id(
                "evidence",
                {
                    "snapshotId": snapshot.snapshot_id,
                    "factId": supported.fact_id,
                    "path": evidence.path,
                    "startLine": evidence.start_line,
                    "endLine": evidence.end_line,
                    "extractor": evidence.extractor,
                    "extractorVersion": evidence.extractor_version,
                },
            )
            finding_id = _stable_id(
                "finding",
                {
                    "snapshotId": snapshot.snapshot_id,
                    "code": diagnostic.code,
                    "producer": diagnostic.producer,
                    "message": diagnostic.message,
                    "factId": supported.fact_id,
                    "evidenceId": evidence_id,
                },
            )
            findings.append(
                ReviewFinding(
                    id=finding_id,
                    category=category,
                    severity=DIAGNOSTIC_SEVERITY_MAPPING[diagnostic.severity],
                    title=title,
                    explanation=diagnostic.message,
                    path=evidence.path,
                    start_line=evidence.start_line,
                    end_line=evidence.end_line,
                    snapshot_id=snapshot.snapshot_id,
                    fact_id=supported.fact_id,
                    evidence_id=evidence_id,
                    extractor_name=evidence.extractor,
                    extractor_version=evidence.extractor_version,
                    diagnostic_code=diagnostic.code,
                    rule_id=f"engineering-review.v2/{diagnostic.code}",
                    remediation_guidance=remediation,
                    provenance=provenance,
                    evidence=ReviewEvidenceReference(
                        evidence_id=evidence_id,
                        snapshot_id=snapshot.snapshot_id,
                        fact_id=supported.fact_id,
                        path=evidence.path,
                        start_line=evidence.start_line,
                        end_line=evidence.end_line,
                        extractor_name=evidence.extractor,
                        extractor_version=evidence.extractor_version,
                    ),
                )
            )

        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        findings.sort(
            key=lambda item: (
                severity_rank[item.severity],
                item.category,
                item.path,
                item.start_line,
                item.diagnostic_code,
                item.id,
            )
        )

        categories = self._categories(snapshot.snapshot_id, findings, diagnostics)
        states = Counter(category.state for category in categories)
        severities = Counter(finding.severity for finding in findings)
        count = len(findings)
        message = (
            f"{count} evidence-backed finding{' was' if count == 1 else 's were'} identified in this revision. "
            "Security vulnerability scanning was not performed."
        )
        manifest = build_manifest(snapshot)
        return EngineeringReviewResponse(
            repository_id=record.id,
            repository_name=record.name,
            revision_kind=snapshot.revision_kind,  # type: ignore[arg-type]
            revision_value=snapshot.revision_value,
            snapshot_id=snapshot.snapshot_id,
            snapshot_schema_version=snapshot.schema_version,
            canonical_graph_hash=snapshot.canonical_graph_hash,
            manifest_digest=manifest_digest(manifest),
            provenance=provenance,
            generated_at=snapshot.sealed_at,
            assessment_status="partially_assessed",
            categories=categories,
            findings=findings,
            summary=ReviewSummary(
                message=message,
                findings_by_severity=ReviewSeverityCounts(
                    info=severities["info"],
                    low=severities["low"],
                    medium=severities["medium"],
                    high=severities["high"],
                    critical=severities["critical"],
                ),
                assessed_categories=states["assessed"],
                partially_assessed_categories=states["partially_assessed"],
                not_assessed_categories=states["not_assessed"],
                insufficient_evidence_categories=states["insufficient_evidence"],
                evidence_backed_finding_count=count,
                omitted_unsupported_diagnostic_count=omitted,
            ),
        )

    def _evidence_by_fact(
        self,
        snapshot_id: str,
        diagnostics: list[RiDiagnostic],
    ) -> dict[str, list[RiEvidence]]:
        observation_ids = {
            value
            for diagnostic in diagnostics
            for value in [(diagnostic.details or {}).get("observation_id")]
            if isinstance(value, str)
        }
        node_keys = {
            value
            for diagnostic in diagnostics
            for value in (diagnostic.subject_key, diagnostic.object_key)
            if value is not None
        }
        node_keys.update(f"file:{diagnostic.path}" for diagnostic in diagnostics if diagnostic.path)

        observations = list(
            self.snapshots.db.scalars(
                select(RiObservation).where(
                    RiObservation.snapshot_id == snapshot_id,
                    RiObservation.observation_id.in_(observation_ids),
                )
            ).all()
        ) if observation_ids else []
        nodes = list(
            self.snapshots.db.scalars(
                select(RiNode).where(
                    RiNode.snapshot_id == snapshot_id,
                    RiNode.stable_key.in_(node_keys),
                )
            ).all()
        ) if node_keys else []

        observation_identity = {item.id: item.observation_id for item in observations}
        node_identity = {item.id: item.stable_key for item in nodes}
        if not observation_identity and not node_identity:
            return {}
        conditions = []
        if observation_identity:
            conditions.append(RiEvidence.observation_ref.in_(observation_identity))
        if node_identity:
            conditions.append(RiEvidence.node_ref.in_(node_identity))
        rows = self.snapshots.db.scalars(
            select(RiEvidence)
            .where(RiEvidence.snapshot_id == snapshot_id, or_(*conditions))
            .order_by(
                RiEvidence.path,
                RiEvidence.start_line,
                RiEvidence.end_line,
                RiEvidence.extractor,
                RiEvidence.extractor_version,
                RiEvidence.id,
            )
        ).all()
        grouped: dict[str, list[RiEvidence]] = defaultdict(list)
        for evidence in rows:
            fact_id = (
                observation_identity.get(evidence.observation_ref)
                if evidence.observation_ref is not None
                else node_identity.get(evidence.node_ref)
            )
            if fact_id is not None:
                grouped[fact_id].append(evidence)
        return dict(grouped)

    @staticmethod
    def _support_for(
        diagnostic: RiDiagnostic,
        evidence_by_fact: dict[str, list[RiEvidence]],
    ) -> _SupportedEvidence | None:
        observation_id = (diagnostic.details or {}).get("observation_id")
        candidates = [
            value
            for value in (
                observation_id if isinstance(observation_id, str) else None,
                diagnostic.subject_key,
                diagnostic.object_key,
                f"file:{diagnostic.path}" if diagnostic.path else None,
            )
            if value is not None
        ]
        for fact_id in candidates:
            for evidence in evidence_by_fact.get(fact_id, []):
                if diagnostic.path is not None and evidence.path != diagnostic.path:
                    continue
                if diagnostic.span_start_line is not None and (
                    evidence.start_line != diagnostic.span_start_line
                    or evidence.end_line != diagnostic.span_end_line
                ):
                    continue
                return _SupportedEvidence(fact_id=fact_id, evidence=evidence)
        return None

    def _categories(
        self,
        snapshot_id: str,
        findings: list[ReviewFinding],
        diagnostics: list[RiDiagnostic],
    ) -> list[ReviewCategoryAssessment]:
        finding_counts = Counter(finding.category for finding in findings)
        diagnostic_codes = {diagnostic.code for diagnostic in diagnostics}
        dependency_count = self.snapshots.db.scalar(
            select(RiNode.id)
            .where(RiNode.snapshot_id == snapshot_id, RiNode.node_kind == "dependency")
            .limit(1)
        )
        file_count = self.snapshots.db.scalar(
            select(RiNode.id)
            .where(RiNode.snapshot_id == snapshot_id, RiNode.node_kind == "file")
            .limit(1)
        )

        states: dict[ReviewCategoryId, tuple[AssessmentState, str]] = {
            "architecture_boundaries": (
                "partially_assessed",
                "Observed nodes and resolved relationships are available; no architectural boundary rating is produced.",
            ),
            "relationship_resolution": (
                "assessed",
                "Resolver diagnostics were assessed and only same-snapshot evidence-backed diagnostics became findings.",
            ),
            "source_extraction": (
                "partially_assessed" if diagnostic_codes else "assessed",
                "Extractor diagnostics were assessed; diagnostics without an authentic line-addressed evidence span remain omitted.",
            ),
            "dependency_declarations": (
                "partially_assessed" if dependency_count is not None else "insufficient_evidence",
                "Declared dependencies are inventoried when present. Vulnerability and outdated-version assessments were not performed.",
            ),
            "security_vulnerability_scanning": (
                "not_assessed",
                "No vulnerability database, advisory feed, lockfile audit, or exploitability scanner was run for this revision.",
            ),
            "authentication_evidence": (
                "partially_assessed",
                "Authentication-relevant observed facts are available, but exploitability and security posture were not assessed.",
            ),
            "repository_structure": (
                "partially_assessed" if file_count is not None else "insufficient_evidence",
                "The sealed file inventory is available; maintainability and code quality were not inferred from filenames or size.",
            ),
            "analysis_integrity": (
                "assessed",
                "The selected snapshot is sealed, revision-bound, and has a canonical graph hash.",
            ),
        }
        return [
            ReviewCategoryAssessment(
                id=category_id,
                label=_CATEGORY_LABELS[category_id],
                state=states[category_id][0],
                explanation=states[category_id][1],
                finding_count=finding_counts[category_id],
            )
            for category_id in _CATEGORY_LABELS
        ]
