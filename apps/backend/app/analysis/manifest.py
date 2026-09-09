"""Build and verify revision manifests from sealed snapshots (#113)."""

from app.intelligence.canonical import canonical_json_bytes, sha256_prefixed
from app.intelligence.query_service import SnapshotQueryService
from app.models.snapshot import RiSnapshot
from app.schemas.manifest import (
    VERIFICATION_METHOD,
    ManifestExtractor,
    RevisionManifest,
    RevisionManifestResponse,
    RevisionManifestVerificationResponse,
)

_SEALED_NOTE = (
    "This digest is a SHA-256 over the canonical JSON encoding of the manifest "
    "fields above. It lets you confirm that an exported manifest still matches "
    "the snapshot stored by this deployment. It is a content hash, not a "
    "digital signature: nothing is signed and no key verification is involved, "
    "so it does not prove authorship or protect against an operator who can "
    "modify the stored snapshot."
)
_UNSEALED_NOTE = (
    "This snapshot is not sealed, so it has no canonical graph hash and cannot "
    "be used as a verifiable revision identity."
)


def _extractors(snapshot: RiSnapshot) -> list[ManifestExtractor]:
    """Split ``name@version`` producer entries into structured extractors.

    A producer without a version is reported with an empty version rather than
    guessing one, so the manifest never invents provenance.
    """

    extractors: list[ManifestExtractor] = []
    for entry in snapshot.producer_version_set or []:
        text = str(entry)
        name, separator, version = text.rpartition("@")
        if not separator:
            name, version = text, ""
        extractors.append(ManifestExtractor(name=name, version=version))
    return sorted(extractors, key=lambda item: (item.name, item.version))


def build_manifest(snapshot: RiSnapshot) -> RevisionManifest:
    return RevisionManifest(
        repository_id=snapshot.repository_id,
        revision_kind=snapshot.revision_kind,  # type: ignore[arg-type]
        revision_value=snapshot.revision_value,
        revision_ref=snapshot.revision_ref,
        snapshot_id=snapshot.snapshot_id,
        snapshot_schema_version=snapshot.schema_version,
        extractors=_extractors(snapshot),
        producer_set_hash=snapshot.producer_set_hash,
        config_hash=snapshot.config_hash,
        canonical_graph_hash=snapshot.canonical_graph_hash,
        created_at=snapshot.created_at,
        sealed_at=snapshot.sealed_at,
    )


def manifest_digest(manifest: RevisionManifest) -> str:
    """Deterministic digest over the manifest body.

    Uses the same canonical JSON encoding the snapshot store uses for its own
    hashes, so the digest is stable across processes, machines and orderings.
    """

    payload = manifest.model_dump(mode="json", by_alias=True)
    return sha256_prefixed(canonical_json_bytes(payload))


class RevisionManifestService:
    """Owner-scoped manifest reads. Ownership is enforced by the query service."""

    def __init__(self, snapshots: SnapshotQueryService) -> None:
        self.snapshots = snapshots

    def _current_revision_snapshot(self, repository_id: str) -> RiSnapshot:
        # The same resolution Review and Insights use, so the manifest always
        # names the revision those surfaces describe. Resolving "latest sealed"
        # independently let the manifest advertise a superseded revision while
        # Review and Insights reported 404 for the current one. A repository
        # owned by someone else stays indistinguishable from one that has never
        # been analysed.
        return self.snapshots.require_sealed_snapshot_for_current_revision(repository_id)

    def read(self, repository_id: str) -> RevisionManifestResponse:
        snapshot = self._current_revision_snapshot(repository_id)
        manifest = build_manifest(snapshot)
        sealed = snapshot.canonical_graph_hash is not None
        return RevisionManifestResponse(
            manifest=manifest,
            manifest_digest=manifest_digest(manifest),
            verification_method=VERIFICATION_METHOD,
            verification_state="verified" if sealed else "unverifiable",
            verification_note=_SEALED_NOTE if sealed else _UNSEALED_NOTE,
        )

    def verify(
        self,
        repository_id: str,
        submitted: RevisionManifest,
        submitted_digest: str,
    ) -> RevisionManifestVerificationResponse:
        """Re-check a previously exported manifest against stored facts.

        Two independent checks must both pass: the submitted digest has to be
        the digest of the submitted body (so tampering with a field is caught
        even if the digest was left alone), and the submitted body has to equal
        the manifest rebuilt from the stored snapshot (so a self-consistent but
        fabricated manifest is caught too).

        The comparison is against the snapshot the manifest *names*, not against
        whichever snapshot is newest. A manifest kept from before a re-analysis
        is authentic and must be reported as authentic; calling it a mismatch
        would tell a user their evidence had been altered when only the
        repository moved on. That case is ``superseded``, and it is reported
        separately from tampering.
        """

        current = self._current_revision_snapshot(repository_id)

        recomputed = manifest_digest(submitted)
        if recomputed != submitted_digest:
            # Reported before any lookup: a body that does not match its own
            # digest has been altered regardless of which snapshot it names.
            return RevisionManifestVerificationResponse(
                verification_state="mismatch",
                matches_stored_snapshot=False,
                mismatched_fields=self._mismatched_fields(build_manifest(current), submitted),
                detail=(
                    "The supplied digest is not the digest of the supplied manifest. "
                    "The manifest content has been altered."
                ),
            )

        named = self.snapshots.sealed_snapshot_for_owner(repository_id, submitted.snapshot_id)
        if named is None:
            return RevisionManifestVerificationResponse(
                verification_state="mismatch",
                matches_stored_snapshot=False,
                mismatched_fields=self._mismatched_fields(build_manifest(current), submitted),
                detail=(
                    "This repository has no sealed snapshot with the identity this manifest "
                    "names, so the manifest cannot be confirmed against stored facts."
                ),
            )

        mismatched = self._mismatched_fields(build_manifest(named), submitted)
        if mismatched:
            return RevisionManifestVerificationResponse(
                verification_state="mismatch",
                matches_stored_snapshot=False,
                mismatched_fields=mismatched,
                detail=(
                    "The manifest is internally consistent but does not match the snapshot stored for this repository."
                ),
            )
        if named.snapshot_id != current.snapshot_id:
            return RevisionManifestVerificationResponse(
                verification_state="superseded",
                matches_stored_snapshot=True,
                mismatched_fields=[],
                detail=(
                    "The manifest matches a sealed snapshot stored for this repository, but "
                    "that snapshot is no longer the current revision. It remains a valid "
                    "record of the revision it names."
                ),
            )
        return RevisionManifestVerificationResponse(
            verification_state="verified",
            matches_stored_snapshot=True,
            mismatched_fields=[],
            detail="The manifest matches the sealed snapshot stored for this repository.",
        )

    @staticmethod
    def _mismatched_fields(stored: RevisionManifest, submitted: RevisionManifest) -> list[str]:
        stored_fields = stored.model_dump(mode="json", by_alias=True)
        submitted_fields = submitted.model_dump(mode="json", by_alias=True)
        return sorted(key for key in stored_fields if stored_fields[key] != submitted_fields.get(key))
