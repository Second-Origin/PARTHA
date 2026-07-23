from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationServiceError
from app.extraction.base import logical_line_count
from app.intelligence import canonical
from app.intelligence.query_service import SnapshotQueryService
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.evidence import EvidenceSourceResponse
from app.services.repository_service import RepositoryService


class EvidenceSourceService:
    """Serve evidence-citation source text bound to its exact cited snapshot (#95).

    A citation names a snapshot, fact, path, and line span. This service proves
    both that the citation is stored and that the available file bytes match
    the content hash sealed on that snapshot's file fact. It never substitutes
    changed repository content, and it never silently narrows or widens the
    requested span -- an unprovable citation returns an explicit
    ``status="unavailable"`` instead.
    """

    def __init__(
        self,
        repository: RepositoryRepository,
        snapshots: SnapshotQueryService,
        files: RepositoryService,
        owner_id: str,
    ) -> None:
        self.repository = repository
        self.snapshots = snapshots
        self.files = files
        self.owner_id = owner_id

    def read(
        self,
        repository_id: str,
        snapshot_id: str,
        fact_id: str,
        path: str,
        start_line: int,
        end_line: int,
    ) -> EvidenceSourceResponse:
        if start_line < 1 or end_line < start_line:
            raise ValidationServiceError(
                "Requested line range is invalid.",
                {"startLine": start_line, "endLine": end_line},
            )

        record = self._get_record(repository_id)
        # metadata() is owner-scoped, requires a sealed ("completed") snapshot,
        # and rejects an unsupported schema version -- the same guarantees
        # every other snapshot-query consumer already relies on.
        snapshot = self.snapshots.metadata(snapshot_id)
        if snapshot.repository_id != repository_id:
            # A real snapshot, but for a *different* repository: the same 404
            # as a missing one, so a cross-repository citation never
            # discloses that the snapshot exists.
            raise NotFoundError("Snapshot not found.", {"snapshotId": snapshot_id})

        def unavailable(reason: str) -> EvidenceSourceResponse:
            return EvidenceSourceResponse(
                schema_version="evidence-source.v1",
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                fact_id=fact_id,
                revision_kind=snapshot.revision_kind,
                revision_value=snapshot.revision_value,
                path=path,
                start_line=start_line,
                end_line=end_line,
                status="unavailable",
                reason=reason,
            )

        # `fk_ri_snapshots_repository_revision` (a composite foreign key from
        # ri_snapshots(repository_id, revision_kind, revision_value) to
        # repositories(id, revision_kind, revision_value)) already makes this
        # divergence impossible at the database level for any snapshot still
        # linked to its repository. This check stays as explicit
        # defense-in-depth -- e.g. against a future schema change -- rather
        # than relying solely on a constraint this code doesn't own.
        if record.revision_kind != snapshot.revision_kind or record.revision_value != snapshot.revision_value:
            return unavailable(
                "The repository's current stored revision no longer matches the exact "
                "revision this citation's snapshot was sealed against."
            )

        if not self.snapshots.has_evidence_reference(snapshot, fact_id, path, start_line, end_line):
            return unavailable("This exact fact and source span are not part of the cited snapshot's evidence.")

        try:
            # Reuses the existing owner-scoped path-traversal, binary, image,
            # and size-truncation protections unchanged; a genuine path-escape
            # attempt still raises ValidationServiceError (422) from here.
            file_response = self.files.read_file(repository_id, path)
        except NotFoundError:
            return unavailable("The exact source for this revision is no longer available.")

        if file_response.is_binary or file_response.is_image:
            return unavailable("The cited path is not a text source file.")

        line_count = logical_line_count(file_response.content)
        if file_response.truncated or end_line > line_count:
            return unavailable("The cited line span is outside the available source content.")

        sealed_content_hash = self.snapshots.source_content_hash(snapshot, path)
        current_content_hash = canonical.sha256_prefixed(file_response.content.encode("utf-8"))
        if sealed_content_hash is None or current_content_hash != sealed_content_hash:
            return unavailable(
                "The available source bytes do not match the content sealed into this snapshot."
            )

        return EvidenceSourceResponse(
            schema_version="evidence-source.v1",
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            fact_id=fact_id,
            revision_kind=snapshot.revision_kind,
            revision_value=snapshot.revision_value,
            path=path,
            start_line=start_line,
            end_line=end_line,
            status="ready",
            content=file_response.content,
            truncated=file_response.truncated,
            size=file_response.size,
        )

    def _get_record(self, repository_id: str):
        # get_for_owner returns None both when the repository does not exist
        # and when it belongs to another user, so a cross-user request gets
        # the same 404 as a missing one and never learns the resource exists.
        record = self.repository.get_for_owner(repository_id, self.owner_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": repository_id})
        return record
