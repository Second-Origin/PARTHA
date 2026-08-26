"""Deterministic, revision-bound Engineering Review generation (#154).

The legacy implementation subtracted arbitrary severity costs from 100 and
generated generic recommendations from mutable repository metadata.  This
builder deliberately has no dependency on a mutable compatibility read model.
It emits only sealed ``ri.v1`` diagnostics that have an authentic supporting
evidence span in the same snapshot.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select

from app.analysis.manifest import build_manifest, manifest_digest
from app.intelligence.canonical import canonical_json_bytes
from app.intelligence.query_service import SnapshotQueryService, batched_ids
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiDiagnostic, RiEvidence, RiNode, RiObservation
from app.schemas.review import (
    AssessmentState,
    EngineeringReviewResponse,
    ReviewCategoryAssessment,
    ReviewCategoryId,
    ReviewEvidenceReference,
    ReviewFinding,
    ReviewPagination,
    ReviewProvenance,
    ReviewSeverity,
    ReviewSeverityCounts,
    ReviewSummary,
    ReviewSupportStatus,
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

#: Codes whose category is source extraction, used to state that category's
#: assessment from extraction evidence rather than from unrelated diagnostics.
_SOURCE_EXTRACTION_CODES = frozenset(code for code, rule in _RULES.items() if rule[0] == "source_extraction")

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
    #: ``supported`` means the evidence span is the diagnostic's own recorded
    #: span. ``file_scoped`` means the diagnostic named a file but no span, so
    #: the finding is honestly scoped to the whole file and says so.
    support_status: ReviewSupportStatus


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"{prefix}:{digest}"


def _overall_assessment_status(states: Counter[AssessmentState]) -> AssessmentState:
    """Summarise the category states instead of asserting a fixed status.

    A constant here would claim a coverage level the categories may not support,
    which is the same class of unearned claim the v2 contract removed.
    """

    if states["assessed"] and not (
        states["partially_assessed"] or states["not_assessed"] or states["insufficient_evidence"]
    ):
        return "assessed"
    if states["assessed"] or states["partially_assessed"]:
        return "partially_assessed"
    if states["insufficient_evidence"]:
        return "insufficient_evidence"
    return "not_assessed"


class EngineeringReviewBuilder:
    """Build the public review solely from an owner-scoped sealed snapshot."""

    def __init__(self, snapshots: SnapshotQueryService) -> None:
        self.snapshots = snapshots

    def build(
        self,
        record: RepositoryRecord,
        *,
        category: ReviewCategoryId | None = None,
        severity: ReviewSeverity | None = None,
        diagnostic_code: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> EngineeringReviewResponse:
        snapshot = self.snapshots.require_sealed_snapshot_for_current_revision(record.id)

        # Only diagnostics with a rule can become findings, so only those are
        # hydrated. Diagnostics without a rule are counted in SQL instead: a
        # snapshot can hold far more diagnostic rows than a review will ever
        # publish, and loading all of them to discard most was unbounded.
        diagnostics = list(
            self.snapshots.db.scalars(
                select(RiDiagnostic)
                .where(
                    RiDiagnostic.snapshot_id == snapshot.snapshot_id,
                    RiDiagnostic.code.in_(_RULES),
                )
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
        omitted_without_rule = (
            self.snapshots.db.scalar(
                select(func.count(RiDiagnostic.id)).where(
                    RiDiagnostic.snapshot_id == snapshot.snapshot_id,
                    RiDiagnostic.code.not_in(_RULES),
                )
            )
            or 0
        )
        evidence_by_fact = self._evidence_by_fact(snapshot.snapshot_id, diagnostics)
        provenance = ReviewProvenance(
            snapshot_id=snapshot.snapshot_id,
            snapshot_schema_version=snapshot.schema_version,
            canonical_graph_hash=snapshot.canonical_graph_hash,
        )

        findings: list[ReviewFinding] = []
        omitted = omitted_without_rule
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
                    support_status=supported.support_status,
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

        # Assessment matrix, severity chips, and the summary message always
        # describe the whole sealed snapshot -- filtering/pagination below
        # narrows only which findings are returned in this response page, the
        # same split the frontend's own client-side filters already made.
        categories = self._categories(snapshot.snapshot_id, findings, diagnostics)
        states = Counter(category.state for category in categories)
        severities = Counter(finding.severity for finding in findings)
        count = len(findings)
        file_scoped = sum(1 for finding in findings if finding.support_status == "file_scoped")
        message = (
            f"{count} evidence-backed finding{' was' if count == 1 else 's were'} identified in this revision. "
            "Security vulnerability scanning was not performed."
        )
        manifest = build_manifest(snapshot)

        matched = [
            finding
            for finding in findings
            if (category is None or finding.category == category)
            and (severity is None or finding.severity == severity)
            and (diagnostic_code is None or finding.diagnostic_code == diagnostic_code)
        ]
        total_matched = len(matched)
        # offset/limit are None only for the internal (non-API) callers that
        # need the complete matched set in one call -- the PDF/JSON export
        # path (#154), and the SQL-batching test that calls _evidence_by_fact
        # directly. Every HTTP request supplies both explicitly (see the
        # /analysis/{repository_id}/review route), so a real client always
        # gets a bounded page.
        page_offset = 0 if offset is None else offset
        page_limit = total_matched if limit is None else limit
        page_findings = matched[page_offset : page_offset + page_limit]
        pagination = ReviewPagination(offset=page_offset, limit=page_limit, total=total_matched)
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
            assessment_status=_overall_assessment_status(states),
            categories=categories,
            findings=page_findings,
            pagination=pagination,
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
                file_scoped_finding_count=file_scoped,
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

        # Every id set below grows with repository size, so each read is split
        # into bounded batches. Binding them in one statement exceeded SQLite's
        # per-statement parameter cap on large snapshots, turning a review into
        # a 500 rather than a bounded set of queries.
        observation_identity: dict[int, str] = {}
        for batch in batched_ids(sorted(observation_ids)):
            observation_identity.update(
                {
                    item.id: item.observation_id
                    for item in self.snapshots.db.scalars(
                        select(RiObservation).where(
                            RiObservation.snapshot_id == snapshot_id,
                            RiObservation.observation_id.in_(batch),
                        )
                    ).all()
                }
            )
        node_identity: dict[int, str] = {}
        for batch in batched_ids(sorted(node_keys)):
            node_identity.update(
                {
                    item.id: item.stable_key
                    for item in self.snapshots.db.scalars(
                        select(RiNode).where(
                            RiNode.snapshot_id == snapshot_id,
                            RiNode.stable_key.in_(batch),
                        )
                    ).all()
                }
            )

        if not observation_identity and not node_identity:
            return {}
        grouped: dict[str, list[RiEvidence]] = defaultdict(list)
        for column, identity in (
            (RiEvidence.observation_ref, observation_identity),
            (RiEvidence.node_ref, node_identity),
        ):
            for batch in batched_ids(sorted(identity)):
                rows = self.snapshots.db.scalars(
                    select(RiEvidence)
                    .where(RiEvidence.snapshot_id == snapshot_id, column.in_(batch))
                    .order_by(
                        RiEvidence.path,
                        RiEvidence.start_line,
                        RiEvidence.end_line,
                        RiEvidence.extractor,
                        RiEvidence.extractor_version,
                        RiEvidence.id,
                    )
                ).all()
                for evidence in rows:
                    fact_id = identity.get(
                        evidence.observation_ref if column is RiEvidence.observation_ref else evidence.node_ref
                    )
                    if fact_id is not None:
                        grouped[fact_id].append(evidence)
        # Batching splits the ordered read, so restore the documented ordering
        # per fact: support selection must not depend on batch boundaries.
        for rows in grouped.values():
            rows.sort(
                key=lambda evidence: (
                    evidence.path,
                    evidence.start_line,
                    evidence.end_line,
                    evidence.extractor,
                    evidence.extractor_version,
                    evidence.id,
                )
            )
        return dict(grouped)

    @staticmethod
    def _support_for(
        diagnostic: RiDiagnostic,
        evidence_by_fact: dict[str, list[RiEvidence]],
    ) -> _SupportedEvidence | None:
        """Find evidence that genuinely addresses this diagnostic, or nothing.

        A finding's ``path``/``startLine``/``endLine`` are presented to a user as
        the location of the problem, so they may only come from evidence that
        actually addresses the diagnostic:

        * A diagnostic that recorded a span is supported only by evidence at
          exactly that path and span.
        * A diagnostic that recorded a path but no span (``RI-SRC-MALFORMED``
          and ``RI-LIMIT-SKIP`` are file-level by construction) is supported
          only by file-granularity evidence for that same path, and the result
          is marked ``file_scoped`` so the whole-file span is never presented as
          a line-addressed finding.
        * A diagnostic with neither is unsupported. Borrowing whichever span
          sorted first would fabricate a location, which is the exact failure
          this contract exists to prevent.
        """

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
        if diagnostic.path is None:
            return None

        has_span = diagnostic.span_start_line is not None
        for fact_id in candidates:
            for evidence in evidence_by_fact.get(fact_id, []):
                if evidence.path != diagnostic.path:
                    continue
                if has_span:
                    if (
                        evidence.start_line != diagnostic.span_start_line
                        or evidence.end_line != diagnostic.span_end_line
                    ):
                        continue
                    return _SupportedEvidence(fact_id=fact_id, evidence=evidence, support_status="supported")
                if evidence.granularity != "file":
                    continue
                return _SupportedEvidence(fact_id=fact_id, evidence=evidence, support_status="file_scoped")
        return None

    def _categories(
        self,
        snapshot_id: str,
        findings: list[ReviewFinding],
        diagnostics: list[RiDiagnostic],
    ) -> list[ReviewCategoryAssessment]:
        finding_counts = Counter(finding.category for finding in findings)
        has_extraction_diagnostics = any(diagnostic.code in _SOURCE_EXTRACTION_CODES for diagnostic in diagnostics)
        has_dependency_nodes = (
            self.snapshots.db.scalar(
                select(RiNode.id).where(RiNode.snapshot_id == snapshot_id, RiNode.node_kind == "dependency").limit(1)
            )
            is not None
        )
        has_file_nodes = (
            self.snapshots.db.scalar(
                select(RiNode.id).where(RiNode.snapshot_id == snapshot_id, RiNode.node_kind == "file").limit(1)
            )
            is not None
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
                "partially_assessed" if has_extraction_diagnostics else "assessed",
                "Extractor diagnostics were assessed; diagnostics without an authentic line-addressed evidence span remain omitted.",
            ),
            "dependency_declarations": (
                "partially_assessed" if has_dependency_nodes else "insufficient_evidence",
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
                "partially_assessed" if has_file_nodes else "insufficient_evidence",
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
