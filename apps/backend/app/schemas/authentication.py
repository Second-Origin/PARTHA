from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel

AuthSchemaVersion = Literal["auth-explanation.v1"]
AuthClaimKind = Literal["route", "middleware", "service", "model", "dependency"]
AuthConfidence = Literal["observed", "heuristic"]
AuthStatus = Literal["ready", "missing_snapshot"]


class AuthEvidenceRef(CamelModel):
    snapshot_id: str
    fact_id: str
    path: str
    start_line: int
    end_line: int


class AuthClaim(CamelModel):
    kind: AuthClaimKind
    name: str
    confidence: AuthConfidence
    evidence: list[AuthEvidenceRef]


class AuthRelationship(CamelModel):
    subject: str
    predicate: str
    object: str
    evidence: list[AuthEvidenceRef]


class AuthenticationDiagnostic(CamelModel):
    code: str
    category: str
    severity: Literal["fatal", "error", "warning", "info"]
    message: str
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None


class AuthenticationExplanationResponse(CamelModel):
    schema_version: AuthSchemaVersion
    repository_id: str
    repository_name: str
    revision_kind: str | None
    revision_value: str | None
    snapshot_id: str | None
    status: AuthStatus
    summary: str
    claims: list[AuthClaim] = Field(default_factory=list)
    relationships: list[AuthRelationship] = Field(default_factory=list)
    diagnostics: list[AuthenticationDiagnostic] = Field(default_factory=list)
