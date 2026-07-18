"""Read-only API for immutable, owner-scoped Repository Intelligence snapshots."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_snapshot_query_service
from app.api.openapi import documented_responses
from app.intelligence.query_service import SnapshotQueryService
from app.schemas.intelligence import (
    RiAssertionResponse,
    RiAssertionsResponse,
    RiEdgeResponse,
    RiEvidenceResponse,
    RiEvidenceResponsePage,
    RiNeighboursResponse,
    RiNodeResponse,
    RiPagination,
    RiPathResponse,
    RiPathsResponse,
    RiReferencesResponse,
    RiSnapshotMetadataResponse,
    RiSymbolsResponse,
)

router = APIRouter(
    prefix="/intelligence/v1/snapshots",
    tags=["repository-intelligence"],
    dependencies=[Depends(get_current_user)],
)

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 100
PaginationOffset = Annotated[int, Query(ge=0, description="Zero-based deterministic result offset.")]
PaginationLimit = Annotated[int, Query(ge=1, le=_MAX_LIMIT, description="Maximum 100 results per page.")]


def _metadata(snapshot) -> RiSnapshotMetadataResponse:
    return RiSnapshotMetadataResponse(
        schema_version=snapshot.schema_version,
        snapshot_id=snapshot.snapshot_id,
        repository_id=snapshot.repository_id,
        revision_kind=snapshot.revision_kind,
        revision_value=snapshot.revision_value,
        revision_ref=snapshot.revision_ref,
        state="completed",
        producer_version_set=snapshot.producer_version_set,
        producer_set_hash=snapshot.producer_set_hash,
        config_hash=snapshot.config_hash,
        canonical_graph_hash=snapshot.canonical_graph_hash,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
        sealed_at=snapshot.sealed_at,
    )


def _evidence(snapshot, item, *, fact_kind: str, fact_id: str) -> RiEvidenceResponse:
    return RiEvidenceResponse(
        schema_version=snapshot.schema_version,
        fact_kind=fact_kind,
        fact_id=fact_id,
        path=item.path,
        start_line=item.start_line,
        end_line=item.end_line,
        granularity=item.granularity,
        extractor=item.extractor,
        extractor_version=item.extractor_version,
    )


def _node(snapshot, node, evidence) -> RiNodeResponse:
    return RiNodeResponse(
        stable_key=node.stable_key,
        node_kind=node.node_kind,
        name=node.name,
        language=node.language,
        truth_class=node.truth_class,
        properties=node.properties,
        evidence=[_evidence(snapshot, item, fact_kind="node", fact_id=node.stable_key) for item in evidence.get(node.id, [])],
    )


def _edge(snapshot, edge, evidence, derivations) -> RiEdgeResponse:
    return RiEdgeResponse(
        edge_id=edge.edge_id,
        subject_kind=edge.subject_kind,
        subject_key=edge.subject_key,
        predicate=edge.predicate,
        object_kind=edge.object_kind,
        object_key=edge.object_key,
        truth_class=edge.truth_class,
        producer=edge.producer,
        producer_version=edge.producer_version,
        evidence=[_evidence(snapshot, item, fact_kind="edge", fact_id=edge.edge_id) for item in evidence.get(edge.id, [])],
        derived_from=[{"kind": item.ref_kind, "identity": item.ref_identity} for item in derivations.get(edge.id, [])],
    )


def _assertion(assertion, derivations) -> RiAssertionResponse:
    return RiAssertionResponse(
        assertion_id=assertion.assertion_id,
        subject_kind=assertion.subject_kind,
        subject_key=assertion.subject_key,
        predicate=assertion.predicate,
        value=assertion.value,
        truth_class=assertion.truth_class,
        producer=assertion.producer,
        producer_version=assertion.producer_version,
        derived_from=[{"kind": item.ref_kind, "identity": item.ref_identity} for item in derivations.get(assertion.id, [])],
    )


def _pagination(offset: int, limit: int, total: int) -> RiPagination:
    return RiPagination(offset=offset, limit=limit, total=total)


@router.get(
    "/{snapshot_id}",
    response_model=RiSnapshotMetadataResponse,
    responses=documented_responses(200, "Sealed ri.v1 snapshot metadata.", {"schemaVersion": "ri.v1"}, 401, 404, 422, 429, 500),
)
def get_snapshot(snapshot_id: str, service: SnapshotQueryService = Depends(get_snapshot_query_service)) -> RiSnapshotMetadataResponse:
    return _metadata(service.metadata(snapshot_id))


@router.get(
    "/{snapshot_id}/symbols",
    response_model=RiSymbolsResponse,
    responses=documented_responses(200, "Observed symbol nodes with stored evidence.", {"schemaVersion": "ri.v1", "data": [], "pagination": {"offset": 0, "limit": 50, "total": 0}}, 401, 404, 422, 429, 500),
)
def list_symbols(
    snapshot_id: str,
    service: SnapshotQueryService = Depends(get_snapshot_query_service),
    offset: PaginationOffset = 0,
    limit: PaginationLimit = _DEFAULT_LIMIT,
) -> RiSymbolsResponse:
    snapshot, nodes, total = service.symbols(snapshot_id, offset=offset, limit=limit)
    evidence = service.evidence_for_nodes(snapshot, nodes)
    return RiSymbolsResponse(schema_version=snapshot.schema_version, data=[_node(snapshot, node, evidence) for node in nodes], pagination=_pagination(offset, limit, total))


@router.get(
    "/{snapshot_id}/neighbours",
    response_model=RiNeighboursResponse,
    responses=documented_responses(200, "Stored resolved edges incident to a node.", {"schemaVersion": "ri.v1", "nodeKey": "repo:root", "data": [], "pagination": {"offset": 0, "limit": 50, "total": 0}}, 401, 404, 422, 429, 500),
)
def list_neighbours(
    snapshot_id: str,
    node_key: Annotated[str, Query(alias="nodeKey", min_length=1, max_length=1024)],
    service: SnapshotQueryService = Depends(get_snapshot_query_service),
    offset: PaginationOffset = 0,
    limit: PaginationLimit = _DEFAULT_LIMIT,
) -> RiNeighboursResponse:
    snapshot, edges, total = service.neighbours(snapshot_id, node_key=node_key, offset=offset, limit=limit)
    evidence = service.evidence_for_edges(snapshot, edges)
    derivations = service.derivations_for_edges(snapshot, edges)
    return RiNeighboursResponse(schema_version=snapshot.schema_version, node_key=node_key, data=[_edge(snapshot, edge, evidence, derivations) for edge in edges], pagination=_pagination(offset, limit, total))


@router.get(
    "/{snapshot_id}/references",
    response_model=RiReferencesResponse,
    responses=documented_responses(200, "Stored resolved relationship facts only.", {"schemaVersion": "ri.v1", "data": [], "pagination": {"offset": 0, "limit": 50, "total": 0}}, 401, 404, 422, 429, 500),
)
def list_references(
    snapshot_id: str,
    service: SnapshotQueryService = Depends(get_snapshot_query_service),
    offset: PaginationOffset = 0,
    limit: PaginationLimit = _DEFAULT_LIMIT,
) -> RiReferencesResponse:
    snapshot, edges, total = service.references(snapshot_id, offset=offset, limit=limit)
    evidence = service.evidence_for_edges(snapshot, edges)
    derivations = service.derivations_for_edges(snapshot, edges)
    return RiReferencesResponse(schema_version=snapshot.schema_version, data=[_edge(snapshot, edge, evidence, derivations) for edge in edges], pagination=_pagination(offset, limit, total))


@router.get(
    "/{snapshot_id}/assertions",
    response_model=RiAssertionsResponse,
    responses=documented_responses(200, "Stored inferred assertions with their derivations.", {"schemaVersion": "ri.v1", "data": [], "pagination": {"offset": 0, "limit": 50, "total": 0}}, 401, 404, 422, 429, 500),
)
def list_assertions(
    snapshot_id: str,
    service: SnapshotQueryService = Depends(get_snapshot_query_service),
    offset: PaginationOffset = 0,
    limit: PaginationLimit = _DEFAULT_LIMIT,
) -> RiAssertionsResponse:
    snapshot, assertions, total = service.assertions(snapshot_id, offset=offset, limit=limit)
    derivations = service.derivations_for_assertions(snapshot, assertions)
    return RiAssertionsResponse(schema_version=snapshot.schema_version, data=[_assertion(assertion, derivations) for assertion in assertions], pagination=_pagination(offset, limit, total))


@router.get(
    "/{snapshot_id}/paths",
    response_model=RiPathsResponse,
    responses=documented_responses(200, "Stored file facts with provenance.", {"schemaVersion": "ri.v1", "data": [], "pagination": {"offset": 0, "limit": 50, "total": 0}}, 401, 404, 422, 429, 500),
)
def list_paths(
    snapshot_id: str,
    service: SnapshotQueryService = Depends(get_snapshot_query_service),
    offset: PaginationOffset = 0,
    limit: PaginationLimit = _DEFAULT_LIMIT,
) -> RiPathsResponse:
    snapshot, nodes, total = service.paths(snapshot_id, offset=offset, limit=limit)
    evidence = service.evidence_for_nodes(snapshot, nodes)
    return RiPathsResponse(schema_version=snapshot.schema_version, data=[RiPathResponse(path=node.stable_key.removeprefix("file:"), node=_node(snapshot, node, evidence)) for node in nodes], pagination=_pagination(offset, limit, total))


@router.get(
    "/{snapshot_id}/evidence",
    response_model=RiEvidenceResponsePage,
    responses=documented_responses(200, "Stored evidence spans only.", {"schemaVersion": "ri.v1", "data": [], "pagination": {"offset": 0, "limit": 50, "total": 0}}, 401, 404, 422, 429, 500),
)
def list_evidence(
    snapshot_id: str,
    service: SnapshotQueryService = Depends(get_snapshot_query_service),
    offset: PaginationOffset = 0,
    limit: PaginationLimit = _DEFAULT_LIMIT,
) -> RiEvidenceResponsePage:
    snapshot, rows, total = service.evidence(snapshot_id, offset=offset, limit=limit)
    identities = service.fact_identity_for_evidence(snapshot, rows)
    data = []
    for item in rows:
        if item.node_ref is not None:
            fact_kind, parent_id = "node", item.node_ref
        elif item.edge_ref is not None:
            fact_kind, parent_id = "edge", item.edge_ref
        else:
            fact_kind, parent_id = "observation", item.observation_ref
        fact_id = identities[(fact_kind, parent_id)]
        data.append(_evidence(snapshot, item, fact_kind=fact_kind, fact_id=fact_id))
    return RiEvidenceResponsePage(schema_version=snapshot.schema_version, data=data, pagination=_pagination(offset, limit, total))
