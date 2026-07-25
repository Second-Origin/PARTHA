"""Revision manifest: the verifiable identity of one sealed snapshot (#113).

The manifest answers "which exact repository revision produced this answer, and
by which extractors" in a form a user can copy out, keep, and later check
against the running system.

Verification here is a canonical-hash comparison, not a digital signature.
Nothing in this module signs anything and no key material is involved, so the
manifest proves *integrity against this deployment's stored snapshot* — it does
not prove authorship or protect against an operator who controls the database.
The wording of ``VERIFICATION_METHOD`` is deliberately literal for that reason.
"""

from datetime import datetime
from typing import Literal

from app.schemas.base import CamelModel

ManifestSchemaVersion = Literal["revision-manifest.v1"]

#: How ``manifestDigest`` is produced. Not a signature scheme.
VERIFICATION_METHOD = "sha256-canonical-json"

#: ``verified``     the manifest matches the snapshot for the current revision.
#: ``superseded``   the manifest matches a sealed snapshot it names, but that
#:                  snapshot is no longer the repository's current revision.
#:                  The manifest is authentic; only the repository moved on.
#: ``mismatch``     the manifest does not match stored facts.
#: ``unverifiable`` the snapshot is not sealed, so it has no revision identity.
VerificationState = Literal["verified", "superseded", "mismatch", "unverifiable"]


class ManifestExtractor(CamelModel):
    """One producer that contributed facts to the snapshot."""

    name: str
    version: str


class RevisionManifest(CamelModel):
    """The manifest body. Every field is copied from the sealed snapshot.

    This model is what gets hashed into ``manifestDigest``; the digest is
    therefore a function of exactly these fields, in canonical JSON form.
    """

    schema_version: ManifestSchemaVersion = "revision-manifest.v1"
    repository_id: str
    #: How the revision is identified: a git commit, or the content hash of an
    #: uploaded archive.
    revision_kind: Literal["git", "upload"]
    revision_value: str
    revision_ref: str | None = None
    snapshot_id: str
    #: Schema version of the snapshot itself (for example ``ri.v1``).
    snapshot_schema_version: str
    extractors: list[ManifestExtractor]
    producer_set_hash: str
    config_hash: str
    #: Canonical digest of the sealed snapshot graph, computed when the
    #: snapshot was sealed. ``None`` means the snapshot is not sealed and the
    #: manifest cannot be trusted as a revision identity.
    canonical_graph_hash: str | None
    created_at: datetime
    sealed_at: datetime | None


class RevisionManifestResponse(CamelModel):
    manifest: RevisionManifest
    #: ``sha256:<hex>`` over the canonical JSON encoding of ``manifest``.
    manifest_digest: str
    verification_method: str = VERIFICATION_METHOD
    #: ``verified`` when the snapshot is sealed and the digest was recomputed
    #: from stored facts; ``unverifiable`` when the snapshot is not sealed.
    verification_state: VerificationState
    #: Plain-language statement of what the digest does and does not prove.
    verification_note: str


class RevisionManifestVerificationRequest(CamelModel):
    """A manifest a user previously exported, submitted for re-checking."""

    manifest: RevisionManifest
    manifest_digest: str


class RevisionManifestVerificationResponse(CamelModel):
    verification_state: VerificationState
    verification_method: str = VERIFICATION_METHOD
    #: True only when the submitted manifest matches the stored snapshot *and*
    #: the submitted digest matches the recomputed one.
    matches_stored_snapshot: bool
    #: Which manifest fields differ from the currently stored snapshot.
    mismatched_fields: list[str]
    detail: str
