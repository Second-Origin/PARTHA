"""Versioned Repository Intelligence snapshot query responses (#92)."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel


FactKind = Literal["node", "edge", "observation"]


class RiEvidenceResponse(CamelModel):
    schema_version: str
    fact_kind: FactKind
    fact_id: str
    path: str
    start_line: int
    end_line: int
    granularity: Literal["span", "file"]
    extractor: str
    extractor_version: str


class RiNodeResponse(CamelModel):
    stable_key: str
    node_kind: str
    name: str | None = None
    language: str | None = None
    truth_class: Literal["observed"]
    properties: dict | None = None
    evidence: list[RiEvidenceResponse] = Field(default_factory=list)


class RiEdgeResponse(CamelModel):
    edge_id: str
    subject_kind: str
    subject_key: str
    predicate: str
    object_kind: str
    object_key: str
    truth_class: Literal["resolved"]
    producer: str
    producer_version: str
    evidence: list[RiEvidenceResponse] = Field(default_factory=list)
    derived_from: list[dict[str, str]] = Field(default_factory=list)


class RiAssertionResponse(CamelModel):
    assertion_id: str
    subject_kind: str
    subject_key: str
    predicate: str
    value: dict
    truth_class: Literal["inferred"]
    producer: str
    producer_version: str
    derived_from: list[dict[str, str]] = Field(default_factory=list)


class RiPathResponse(CamelModel):
    path: str
    node: RiNodeResponse


class RiPagination(CamelModel):
    offset: int
    limit: int
    total: int


class RiSnapshotMetadataResponse(CamelModel):
    schema_version: str
    snapshot_id: str
    repository_id: str
    revision_kind: Literal["git", "upload"]
    revision_value: str
    revision_ref: str | None = None
    state: Literal["completed"]
    producer_version_set: list[str]
    producer_set_hash: str
    config_hash: str
    canonical_graph_hash: str
    created_at: datetime
    updated_at: datetime
    sealed_at: datetime


class RiSymbolsResponse(CamelModel):
    schema_version: str
    data: list[RiNodeResponse]
    pagination: RiPagination


class RiNeighboursResponse(CamelModel):
    schema_version: str
    node_key: str
    data: list[RiEdgeResponse]
    pagination: RiPagination


class RiReferencesResponse(CamelModel):
    schema_version: str
    data: list[RiEdgeResponse]
    pagination: RiPagination


class RiAssertionsResponse(CamelModel):
    schema_version: str
    data: list[RiAssertionResponse]
    pagination: RiPagination


class RiPathsResponse(CamelModel):
    schema_version: str
    data: list[RiPathResponse]
    pagination: RiPagination


class RiEvidenceResponsePage(CamelModel):
    schema_version: str
    data: list[RiEvidenceResponse]
    pagination: RiPagination
