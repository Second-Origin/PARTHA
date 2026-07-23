"""Evidence-backed authentication explanation (#95).

Reads exclusively through :class:`SnapshotQueryService`: no filesystem read,
no working-tree fallback, no legacy ``repo_metadata['intelligence']`` read,
and no second parser or consumer-specific fact store. Every displayed claim
resolves to a real evidence span stored against the exact sealed snapshot
named in the response; a claim with no resolvable evidence is dropped rather
than shown as fact.

Authentication relevance comes from graph connectivity, never from a global
role-name match. A route, service, or model is only ever included when it is
reachable from a resolved ``routes_to`` edge through a resolved ``injects``
edge into a symbol the role classifier has explicitly marked
``auth_dependency`` (#95's guard signal), and — for services/models — through
a chain of resolved ``calls`` edges from that guard. An unrelated route (for
example ``/health``), an unrelated ``*Service``/``*Model`` symbol, or a
generic injected dependency (for example ``Depends(get_database)``) is never
part of that subgraph, so it is never claimed as authentication regardless of
its name or classification.
"""

from __future__ import annotations

from collections import defaultdict, deque

from app.intelligence.query_service import ArchitectureSnapshotFacts, SnapshotQueryService
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiEdge, RiNode
from app.schemas.authentication import (
    AuthChain,
    AuthClaim,
    AuthClaimKind,
    AuthConfidence,
    AuthenticationDiagnostic,
    AuthenticationExplanationResponse,
    AuthEvidenceRef,
    AuthRelationship,
    AuthRelationshipNodeKind,
)

_GUARD_CLASSIFICATION = "auth_dependency"
_SERVICE_CLASSIFICATION = "service"
_MODEL_CLASSIFICATION = "model"
_DIAGNOSTIC_CODES = frozenset(
    {"RI-RES-UNRESOLVED", "RI-RES-AMBIGUOUS", "RI-EXT-UNSUPPORTED", "RI-SRC-MALFORMED"}
)
_MAX_DIAGNOSTICS = 50


def _display_name(node: RiNode) -> str:
    if node.node_kind == "symbol" and node.properties and "route_path" in node.properties:
        return str(node.properties["route_path"])
    return node.name or node.stable_key


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
        return _AuthenticationSubgraphBuilder(record, facts).build()


class _AuthenticationSubgraphBuilder:
    """Select and render the evidence-backed authentication subgraph once.

    One instance is used per request: it walks resolved ``routes_to`` ->
    ``injects`` -> ``calls`` edges starting from every route, keeps only the
    routes that reach an explicit ``auth_dependency`` guard, and — from each
    guard — keeps only the ``calls`` targets that lie on a path to a symbol
    the role classifier marked ``service``/``model``. Nothing reachable is
    assumed relevant; only nodes on a proven path to a classified target (or
    the guard itself) are ever surfaced.
    """

    def __init__(self, record: RepositoryRecord, facts: ArchitectureSnapshotFacts) -> None:
        self.record = record
        self.facts = facts
        self.nodes_by_key: dict[str, RiNode] = {node.stable_key: node for node in facts.nodes}

        self.classifications: dict[str, set[str]] = defaultdict(set)
        for assertion in facts.assertions:
            if assertion.predicate != "classified_as" or assertion.subject_kind != "symbol":
                continue
            classification = str((assertion.value or {}).get("classification", ""))
            if classification:
                self.classifications[assertion.subject_key].add(classification)

        self.injects_by_subject: dict[str, list[RiEdge]] = defaultdict(list)
        self.calls_by_subject: dict[str, list[RiEdge]] = defaultdict(list)
        for edge in facts.edges:
            if edge.predicate == "injects":
                self.injects_by_subject[edge.subject_key].append(edge)
            elif edge.predicate == "calls":
                self.calls_by_subject[edge.subject_key].append(edge)

        self.claims: list[AuthClaim] = []
        self._seen_claim_keys: set[tuple[str, str]] = set()
        self.relationships: list[AuthRelationship] = []
        # Interns one AuthRelationship per (subject, predicate, object): the
        # flat list below only ever gets one entry per key, but every chain
        # that shares the hop still receives the same, complete object --
        # chain completeness never depends on whether another route already
        # claimed this hop first.
        self._relationship_by_key: dict[tuple[str, str, str], AuthRelationship] = {}
        self.chains: list[AuthChain] = []

    def build(self) -> AuthenticationExplanationResponse:
        for route_edge in self._sorted(self.facts.edges, "routes_to"):
            self._process_route(route_edge)

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
            for diagnostic in self.facts.diagnostics
            if diagnostic.code in _DIAGNOSTIC_CODES
        ][:_MAX_DIAGNOSTICS]

        counts = {
            kind: sum(1 for claim in self.claims if claim.kind == kind)
            for kind in ("route", "middleware", "service", "model", "dependency")
        }
        summary = (
            f"Found {counts['route']} authentication-relevant route(s), {counts['middleware']} "
            f"guard dependency(ies), {counts['service']} service(s), and {counts['model']} model(s) "
            "reached from them, each backed by a citation to its exact stored source span."
        )

        return AuthenticationExplanationResponse(
            schema_version="auth-explanation.v1",
            repository_id=self.record.id,
            repository_name=self.record.name,
            revision_kind=self.facts.snapshot.revision_kind,
            revision_value=self.facts.snapshot.revision_value,
            snapshot_id=self.facts.snapshot.snapshot_id,
            status="ready",
            summary=summary,
            claims=self.claims,
            relationships=self.relationships,
            chains=self.chains,
            diagnostics=diagnostics,
        )

    def _process_route(self, route_edge: RiEdge) -> None:
        route_node = self.nodes_by_key.get(route_edge.subject_key)
        handler_node = self.nodes_by_key.get(route_edge.object_key)
        if route_node is None or handler_node is None:
            return
        route_evidence = self._edge_evidence(route_edge)
        if not route_evidence:
            return

        guard_edges = [
            edge
            for edge in self._sorted(self.injects_by_subject.get(handler_node.stable_key, ()), "injects")
            if _GUARD_CLASSIFICATION in self.classifications.get(edge.object_key, ())
        ]

        for guard_edge in guard_edges:
            self._process_guard(route_node, handler_node, route_edge, guard_edge)

    def _process_guard(
        self,
        route_node: RiNode,
        handler_node: RiNode,
        route_edge: RiEdge,
        guard_edge: RiEdge,
    ) -> None:
        guard_node = self.nodes_by_key.get(guard_edge.object_key)
        if guard_node is None:
            return
        guard_evidence = self._edge_evidence(guard_edge)
        if not guard_evidence:
            return

        used_edges = self._reachable_service_model_edges(guard_node)

        # This route genuinely participates in a supported, evidence-backed
        # authentication path: the route claim and its two anchor hops are
        # only ever added here, never unconditionally for every route.
        self._add_claim("route", route_node, "observed")
        self._add_claim("middleware", guard_node, "heuristic")

        hops: list[AuthRelationship] = []
        route_hop = self._add_relationship(route_node, "route", "routes_to", handler_node, "handler", route_edge)
        if route_hop is not None:
            hops.append(route_hop)
        guard_hop = self._add_relationship(handler_node, "handler", "injects", guard_node, "middleware", guard_edge)
        if guard_hop is not None:
            hops.append(guard_hop)

        for subject_key, object_key, edge in used_edges:
            subject = self.nodes_by_key.get(subject_key)
            obj = self.nodes_by_key.get(object_key)
            if subject is None or obj is None:
                continue
            object_kind = self._role_of(object_key)
            self._add_claim(object_kind, obj, "heuristic")
            hop = self._add_relationship(subject, self._role_of(subject_key), "calls", obj, object_kind, edge)
            if hop is not None:
                hops.append(hop)

        if hops:
            self.chains.append(AuthChain(route=_display_name(route_node), hops=hops))

    def _reachable_service_model_edges(self, guard_node: RiNode) -> list[tuple[str, str, RiEdge]]:
        """BFS the resolved ``calls`` graph from ``guard_node``.

        Returns only the edges that lie on a path from the guard to a symbol
        classified ``service`` or ``model`` — an unrelated call the guard
        happens to make that never reaches a classified target is pruned, not
        surfaced as a guess.
        """

        parent: dict[str, tuple[str, RiEdge]] = {}
        visited: set[str] = {guard_node.stable_key}
        discovered_edges: list[RiEdge] = []
        classified_targets: list[str] = []

        queue: deque[str] = deque([guard_node.stable_key])
        while queue:
            current = queue.popleft()
            for edge in self._sorted(self.calls_by_subject.get(current, ()), "calls"):
                object_key = edge.object_key
                if object_key in visited:
                    continue
                if not self._edge_evidence(edge):
                    continue
                visited.add(object_key)
                parent[object_key] = (current, edge)
                discovered_edges.append(edge)
                queue.append(object_key)
                roles = self.classifications.get(object_key, ())
                if _SERVICE_CLASSIFICATION in roles or _MODEL_CLASSIFICATION in roles:
                    classified_targets.append(object_key)

        used_nodes: set[str] = set()
        for target_key in classified_targets:
            walk_key = target_key
            while walk_key in parent:
                used_nodes.add(walk_key)
                walk_key = parent[walk_key][0]

        return [
            (edge.subject_key, edge.object_key, edge)
            for edge in discovered_edges
            if edge.object_key in used_nodes
        ]

    def _role_of(self, stable_key: str) -> AuthRelationshipNodeKind:
        roles = self.classifications.get(stable_key, ())
        if _GUARD_CLASSIFICATION in roles:
            return "middleware"
        if _SERVICE_CLASSIFICATION in roles:
            return "service"
        if _MODEL_CLASSIFICATION in roles:
            return "model"
        return "dependency"

    @staticmethod
    def _claim_kind_for_role(role: AuthRelationshipNodeKind) -> AuthClaimKind:
        if role == "handler":
            raise ValueError("'handler' is never a claim kind")
        return role

    def _add_claim(self, role: AuthRelationshipNodeKind, node: RiNode, confidence: AuthConfidence) -> None:
        kind = self._claim_kind_for_role(role)
        key = (kind, node.stable_key)
        if key in self._seen_claim_keys:
            return
        evidence = self._node_evidence(node)
        if not evidence:
            # A claim with no resolvable evidence is never displayed as fact.
            return
        self._seen_claim_keys.add(key)
        self.claims.append(AuthClaim(kind=kind, name=_display_name(node), confidence=confidence, evidence=evidence))

    def _add_relationship(
        self,
        subject: RiNode,
        subject_kind: AuthRelationshipNodeKind,
        predicate: str,
        obj: RiNode,
        object_kind: AuthRelationshipNodeKind,
        edge: RiEdge,
    ) -> AuthRelationship | None:
        evidence = self._edge_evidence(edge)
        if not evidence:
            return None
        key = (subject.stable_key, predicate, obj.stable_key)
        existing = self._relationship_by_key.get(key)
        if existing is not None:
            return existing
        relationship = AuthRelationship(
            subject=_display_name(subject),
            subject_kind=subject_kind,
            predicate=predicate,
            object=_display_name(obj),
            object_kind=object_kind,
            evidence=evidence,
        )
        self._relationship_by_key[key] = relationship
        self.relationships.append(relationship)
        return relationship

    def _node_evidence(self, node: RiNode) -> list[AuthEvidenceRef]:
        return [
            AuthEvidenceRef(
                snapshot_id=self.facts.snapshot.snapshot_id,
                fact_id=node.stable_key,
                path=item.path,
                start_line=item.start_line,
                end_line=item.end_line,
            )
            for item in self.facts.node_evidence.get(node.id, [])
        ]

    def _edge_evidence(self, edge: RiEdge) -> list[AuthEvidenceRef]:
        return [
            AuthEvidenceRef(
                snapshot_id=self.facts.snapshot.snapshot_id,
                fact_id=edge.edge_id,
                path=item.path,
                start_line=item.start_line,
                end_line=item.end_line,
            )
            for item in self.facts.edge_evidence.get(edge.id, [])
        ]

    @staticmethod
    def _sorted(edges, predicate: str) -> list[RiEdge]:
        return sorted(
            (edge for edge in edges if edge.predicate == predicate),
            key=lambda edge: (edge.subject_key, edge.object_key, edge.edge_id),
        )
