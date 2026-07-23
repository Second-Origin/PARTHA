from typing import Literal

from app.schemas.base import CamelModel

EvidenceSchemaVersion = Literal["evidence-source.v1"]
EvidenceSourceStatus = Literal["ready", "unavailable"]


class EvidenceSourceResponse(CamelModel):
    """The exact source text a citation points at, bound to its cited snapshot.

    ``status="unavailable"`` covers every case where the exact cited revision
    cannot be honestly displayed (revision mismatch, missing source, out-of-
    range span, binary content): ``content`` is always ``None`` in that case
    rather than falling back to different content under a trusted-looking
    snapshot/revision identity.
    """

    schema_version: EvidenceSchemaVersion
    repository_id: str
    snapshot_id: str
    revision_kind: str | None
    revision_value: str | None
    path: str
    start_line: int
    end_line: int
    status: EvidenceSourceStatus
    reason: str | None = None
    content: str | None = None
    truncated: bool = False
    size: int = 0
