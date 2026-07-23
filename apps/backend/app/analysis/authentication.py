"""Evidence-backed authentication explanation (#95).

Reads exclusively through :class:`SnapshotQueryService`: no filesystem read,
no working-tree fallback, no legacy ``repo_metadata['intelligence']`` read,
and no second parser or consumer-specific fact store. Every displayed claim
resolves to a real evidence span stored against the exact sealed snapshot
named in the response; a claim with no resolvable evidence is dropped rather
than shown as fact.
"""

from __future__ import annotations

from app.intelligence.query_service import ArchitectureSnapshotFacts, SnapshotQueryService
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiEdge, RiNode
from app.schemas.authentication import (
    AuthClaim,
    AuthClaimKind,
    AuthConfidence,
    AuthenticationDiagnostic,
    AuthenticationExplanationResponse,
    AuthEvidenceRef,
    AuthRelationship,
)

_MIDDLEWARE_CLASSIFICATIONS = frozenset({"middleware", "auth_dependency"})
_SERVICE_CLASSIFICATIONS = frozenset({"service"})
_MODEL_CLASSIFICATIONS = frozenset({"model"})
_DIAGNOSTIC_CODES = frozenset(
    {"RI-RES-UNRESOLVED", "RI-RES-AMBIGUOUS", "RI-EXT-UNSUPPORTED", "RI-SRC-MALFORMED"}
)
_MAX_DIAGNOSTICS = 50


class AuthenticationExplanationService:
    """Build the authentication explanation for one owner-scoped repository."""

    def __init__(self, snapshots: SnapshotQueryService) -> None:
        self.snapshots = snapshots

    def explain(self, record: RepositoryRecord) -> AuthenticationExplanationResponse:
        facts = self.snapshots.architecture_facts(record.id)
        if facts is None:
            return AuthenticationExplanationResponse(
                schema_version="auth-explanation.v1",
                repository_id=record.id,
                repository_name=record.name,
                revision_kind=record.revision_kind,
                revision_value=record.revision_value,
                snapshot_id=None,
                status="missing_snapshot",
                summary=(
                    "No sealed repository intelligence snapshot is available for this "
                    "repository yet. Run analysis to produce one before requesting an "
                    "authentication explanation."
                ),
                diagnostics=[
                    AuthenticationDiagnostic(
                        code="AUTH-NO-SNAPSHOT",
                        category="snapshot",
                        severity="info",
                        message="No sealed snapshot exists for this repository's current revision.",
                    )
                ],
            )
        return self._build(record, facts)

    def _build(
        self, record: RepositoryRecord, facts: ArchitectureSnapshotFacts
    ) -> AuthenticationExplanationResponse:
        nodes_by_key: dict[str, RiNode] = {node.stable_key: node for node in facts.nodes}
        claims: list[AuthClaim] = []
        relationships: list[AuthRelationship] = []
        seen_claim_keys: set[tuple[str, str]] = set()

        def node_evidence_refs(node: RiNode) -> list[AuthEvidenceRef]:
            return [
                AuthEvidenceRef(
                    snapshot_id=facts.snapshot.snapshot_id,
                    fact_id=node.stable_key,
                    path=item.path,
                    start_line=item.start_line,
                    end_line=item.end_line,
                )
                for item in facts.node_evidence.get(node.id, [])
            ]

        def edge_evidence_refs(edge: RiEdge) -> list[AuthEvidenceRef]:
            return [
                AuthEvidenceRef(
                    snapshot_id=facts.snapshot.snapshot_id,
                    fact_id=edge.edge_id,
                    path=item.path,
                    start_line=item.start_line,
                    end_line=item.end_line,
                )
                for item in facts.edge_evidence.get(edge.id, [])
            ]

        def add_claim(kind: AuthClaimKind, node: RiNode, confidence: AuthConfidence) -> None:
            key = (kind, node.stable_key)
            if key in seen_claim_keys:
                return
            evidence = node_evidence_refs(node)
            if not evidence:
                # A claim with no resolvable evidence is never displayed as fact.
                return
            seen_claim_keys.add(key)
            claims.append(AuthClaim(kind=kind, name=node.name or node.stable_key, confidence=confidence, evidence=evidence))

        # Routes: symbol nodes carrying a route_path property (extracted directly,
        # never guessed — see PythonExtractor._route_paths).
        for node in facts.nodes:
            if node.node_kind != "symbol" or not node.properties or "route_path" not in node.properties:
                continue
            evidence = node_evidence_refs(node)
            if not evidence:
                continue
            route_key = ("route", node.stable_key)
            if route_key in seen_claim_keys:
                continue
            seen_claim_keys.add(route_key)
            claims.append(
                AuthClaim(
                    kind="route",
                    name=str(node.properties["route_path"]),
                    confidence="observed",
                    evidence=evidence,
                )
            )

        # routes_to: route -> handler symbol (resolved, evidence-backed).
        for edge in facts.edges:
            if edge.predicate != "routes_to":
                continue
            evidence = edge_evidence_refs(edge)
            if not evidence:
                continue
            subject = nodes_by_key.get(edge.subject_key)
            object_ = nodes_by_key.get(edge.object_key)
            if subject is None or object_ is None:
                continue
            subject_name = str((subject.properties or {}).get("route_path") or subject.name or subject.stable_key)
            relationships.append(
                AuthRelationship(
                    subject=subject_name,
                    predicate="routes_to",
                    object=object_.name or object_.stable_key,
                    evidence=evidence,
                )
            )

        # injects: handler -> dependency callable (candidate middleware/guards).
        injected_object_keys: set[str] = set()
        for edge in facts.edges:
            if edge.predicate != "injects":
                continue
            evidence = edge_evidence_refs(edge)
            if not evidence:
                continue
            subject = nodes_by_key.get(edge.subject_key)
            object_ = nodes_by_key.get(edge.object_key)
            if subject is None or object_ is None:
                continue
            injected_object_keys.add(object_.stable_key)
            relationships.append(
                AuthRelationship(
                    subject=subject.name or subject.stable_key,
                    predicate="injects",
                    object=object_.name or object_.stable_key,
                    evidence=evidence,
                )
            )

        # classified_as assertions (role-classifier, #95): service / model /
        # middleware / auth_dependency. Only symbol-level classifications
        # become claims here — file-level classification exists to group
        # architecture modules, not to name authentication symbols. Every
        # assertion's truth_class is "inferred" — surfaced with
        # confidence="heuristic", never as a guaranteed fact.
        for assertion in facts.assertions:
            if assertion.predicate != "classified_as" or assertion.subject_kind != "symbol":
                continue
            node = nodes_by_key.get(assertion.subject_key)
            if node is None:
                continue
            classification = str((assertion.value or {}).get("classification", ""))
            if classification in _MIDDLEWARE_CLASSIFICATIONS:
                add_claim("middleware", node, "heuristic")
            elif classification in _SERVICE_CLASSIFICATIONS:
                add_claim("service", node, "heuristic")
            elif classification in _MODEL_CLASSIFICATIONS:
                add_claim("model", node, "heuristic")

        # An injected dependency the classifier did not confidently tag as an
        # auth guard is still a real, evidenced relationship — surfaced as a
        # plain dependency instead of being silently dropped or mislabeled.
        for key in injected_object_keys:
            node = nodes_by_key.get(key)
            if node is None or ("middleware", key) in seen_claim_keys:
                continue
            add_claim("dependency", node, "heuristic")

        diagnostics = [
            AuthenticationDiagnostic(
                code=diagnostic.code,
                category=diagnostic.category,
                severity=diagnostic.severity,
                message=diagnostic.message,
                path=diagnostic.path,
                start_line=diagnostic.span_start_line,
                end_line=diagnostic.span_end_line,
            )
            for diagnostic in facts.diagnostics
            if diagnostic.code in _DIAGNOSTIC_CODES
        ][:_MAX_DIAGNOSTICS]

        counts = {kind: sum(1 for claim in claims if claim.kind == kind) for kind in ("route", "middleware", "service", "model")}
        summary = (
            f"Found {counts['route']} authentication-relevant route(s), {counts['middleware']} middleware/guard "
            f"dependency(ies), {counts['service']} service(s), and {counts['model']} model(s), each backed by a "
            "citation to its exact stored source span."
        )

        return AuthenticationExplanationResponse(
            schema_version="auth-explanation.v1",
            repository_id=record.id,
            repository_name=record.name,
            revision_kind=facts.snapshot.revision_kind,
            revision_value=facts.snapshot.revision_value,
            snapshot_id=facts.snapshot.snapshot_id,
            status="ready",
            summary=summary,
            claims=claims,
            relationships=relationships,
            diagnostics=diagnostics,
        )
