import base64
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import ConflictServiceError, NotFoundError, ServiceError, ValidationServiceError
from app.github.client import GitHubClient
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.parsers.repository_parser import RepositoryParser
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.repository import (
    GitHubImportRequest,
    RepositoryFileResponse,
    RepositoryListResponse,
    RepositoryResponse,
    RepositoryRevision,
)
from app.storage.local import LocalStorage

MAX_FILE_PREVIEW_BYTES = 512 * 1024

# A git object name is a 40-character lowercase hex SHA-1 (RFC §3.2). ri.v1
# targets the SHA-1 default git produces today.
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
}


class RepositoryService:
    def __init__(
        self,
        repository: RepositoryRepository,
        storage: LocalStorage,
        github: GitHubClient,
        parser: RepositoryParser,
        intelligence: RepositoryIntelligenceEngine,
        settings: Settings,
        owner_id: str,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.github = github
        self.parser = parser
        self.intelligence = intelligence
        self.settings = settings
        self.owner_id = owner_id

    def list_repositories(self) -> RepositoryListResponse:
        records = self.repository.list_for_owner(self.owner_id)
        return RepositoryListResponse(data=[self.to_response(record) for record in records], total=len(records))

    def get_repository(self, repository_id: str) -> RepositoryResponse:
        return self.to_response(self._get_record(repository_id))

    def delete_repository(self, repository_id: str) -> None:
        record = self._get_record(repository_id)
        self.storage.delete_repository(record.local_path)
        self.repository.delete(record)

    def import_github_repository(self, request: GitHubImportRequest) -> RepositoryResponse:
        repository_id = str(uuid4())
        url = self.github.validate_public_url(str(request.url))
        branch = self.github.validate_branch(request.branch)

        # A new commit is a new revision, so duplicate detection is keyed on the
        # resolved commit SHA rather than URL+branch (#87). That requires cloning
        # first: URL+branch is only a fallback when git identity is unavailable,
        # and it must never block importing a genuinely new revision.
        destination = self.storage.reset_repository_path(repository_id)
        try:
            self.github.clone_public_repository(url, destination, branch)
            root = self._resolve_repository_root(destination)
            commit_sha = self.github.read_head_commit(destination)
            revision_kind, revision_value, revision_ref = self._git_revision(destination, commit_sha, branch)
            existing = self.repository.find_by_source_revision_for_owner(url, revision_value, self.owner_id)
            if existing:
                raise ConflictServiceError(
                    "Repository has already been imported.",
                    {"repositoryId": existing.id, "name": existing.name},
                )
            tree, meta, total_size = self.parser.parse(root)
            self._validate_parsed_repository(meta.total_files)
            repository_intelligence = self.intelligence.build(repository_id, self.github.repository_name(url), root, tree, meta, total_size)
        except Exception:
            self.storage.delete_repository_id(repository_id)
            raise

        now = datetime.now(UTC)
        record = RepositoryRecord(
            id=repository_id,
            owner_id=self.owner_id,
            name=self.github.repository_name(url),
            description=None,
            source="github",
            source_url=url,
            branch=branch,
            revision_kind=revision_kind,
            revision_value=revision_value,
            revision_ref=revision_ref,
            local_path=str(root),
            size=total_size,
            file_count=meta.total_files,
            status="analysing",
            analysis_stage="building-file-tree",
            analysis_progress=70,
            uploaded_at=now,
            analysed_at=None,
            repo_metadata=self._metadata_with_intelligence(meta, repository_intelligence),
            file_tree=[node.model_dump(mode="json", by_alias=True, exclude_none=True) for node in tree],
        )
        return self.to_response(self.repository.add(record))

    async def import_uploaded_repository(self, file: UploadFile) -> RepositoryResponse:
        repository_id = str(uuid4())
        repository_name = self._repository_name_from_archive(file.filename or repository_id)

        archive_path = await self.storage.save_upload(repository_id, file, self.settings.max_upload_size_bytes)
        try:
            # Uploads have no git history, so the immutable content hash is the
            # revision. Duplicate detection is keyed on that content hash (#87),
            # not the filename: a genuinely new archive is a new revision even
            # if it is uploaded under a previously-used name.
            content_hash = self._content_hash_for_upload(archive_path)
            existing = self.repository.find_by_revision_for_owner(content_hash, self.owner_id)
            if existing:
                raise ConflictServiceError(
                    "Repository has already been imported.",
                    {"repositoryId": existing.id, "name": existing.name},
                )
            root = self.storage.extract_archive(archive_path, repository_id)
            tree, meta, total_size = self.parser.parse(root)
            self._validate_parsed_repository(meta.total_files)
            repository_intelligence = self.intelligence.build(repository_id, repository_name, root, tree, meta, total_size)
        except Exception:
            self.storage.delete_upload(archive_path)
            self.storage.delete_repository_id(repository_id)
            raise
        self.storage.delete_upload(archive_path)

        now = datetime.now(UTC)
        record = RepositoryRecord(
            id=repository_id,
            owner_id=self.owner_id,
            name=repository_name,
            description=None,
            source="upload",
            source_url=None,
            branch=None,
            revision_kind="upload",
            revision_value=content_hash,
            revision_ref=None,
            local_path=str(root),
            size=total_size,
            file_count=meta.total_files,
            status="analysing",
            analysis_stage="building-file-tree",
            analysis_progress=70,
            uploaded_at=now,
            analysed_at=None,
            repo_metadata=self._metadata_with_intelligence(meta, repository_intelligence),
            file_tree=[node.model_dump(mode="json", by_alias=True, exclude_none=True) for node in tree],
        )
        return self.to_response(self.repository.add(record))

    def read_file(self, repository_id: str, path: str) -> RepositoryFileResponse:
        record = self._get_record(repository_id)
        try:
            root = Path(record.local_path).resolve()
            target = (root / path.lstrip("/\\")).resolve()
        except (OSError, RuntimeError) as exc:
            raise ValidationServiceError("Requested file path cannot be resolved.", {"path": path}) from exc

        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValidationServiceError("Requested file is outside the repository.", {"path": path}) from exc

        try:
            is_file = target.is_file()
        except OSError as exc:
            self._raise_file_read_error(path, exc)
        if not is_file:
            raise NotFoundError("File not found in repository.", {"path": path})

        try:
            size = target.stat().st_size
        except OSError as exc:
            self._raise_file_read_error(path, exc)

        media_type = IMAGE_MEDIA_TYPES.get(target.suffix.lower())
        if media_type is not None:
            if size > MAX_FILE_PREVIEW_BYTES:
                return RepositoryFileResponse(
                    path=path, content="", size=size, truncated=True, is_image=True, media_type=media_type
                )
            try:
                content = base64.b64encode(target.read_bytes()).decode("ascii")
            except OSError as exc:
                self._raise_file_read_error(path, exc)
            return RepositoryFileResponse(
                path=path,
                content=content,
                size=size,
                is_image=True,
                media_type=media_type,
            )

        try:
            with target.open("rb") as handle:
                chunk = handle.read(MAX_FILE_PREVIEW_BYTES)
        except OSError as exc:
            self._raise_file_read_error(path, exc)

        truncated = size > MAX_FILE_PREVIEW_BYTES
        if b"\x00" in chunk:
            return RepositoryFileResponse(path=path, content="", size=size, truncated=truncated, is_binary=True)
        return RepositoryFileResponse(
            path=path,
            content=chunk.decode("utf-8", errors="replace"),
            size=size,
            truncated=truncated,
        )

    def _raise_file_read_error(self, path: str, exc: OSError) -> NoReturn:
        if isinstance(exc, FileNotFoundError):
            raise NotFoundError("File not found in repository.", {"path": path}) from exc
        if isinstance(exc, PermissionError):
            raise ValidationServiceError("File cannot be read due to filesystem permissions.", {"path": path}) from exc
        raise ServiceError("Unable to read file preview.", {"path": path}) from exc

    def to_response(self, record: RepositoryRecord) -> RepositoryResponse:
        revision = None
        if record.revision_kind and record.revision_value:
            revision = RepositoryRevision(
                kind=record.revision_kind,
                value=record.revision_value,
                ref=record.revision_ref,
            )
        return RepositoryResponse(
            id=record.id,
            name=record.name,
            description=record.description,
            source=record.source,
            source_url=record.source_url,
            branch=record.branch,
            size=record.size,
            file_count=record.file_count,
            status=record.status,
            analysis_stage=record.analysis_stage,
            analysis_progress=record.analysis_progress,
            uploaded_at=record.uploaded_at,
            analysed_at=record.analysed_at,
            error_message=record.error_message,
            revision=revision,
            # Revision identity now comes from the first-class column, not the
            # mutable metadata blob (#87). ``commit_sha`` is a compatibility alias.
            commit_sha=record.revision_value,
            meta=record.repo_metadata,
            file_tree=record.file_tree,
        )

    def _get_record(self, repository_id: str) -> RepositoryRecord:
        # get_for_owner returns None both when the repository does not exist and
        # when it belongs to another user, so a cross-user request gets the same
        # 404 as a missing one and never learns the resource exists.
        record = self.repository.get_for_owner(repository_id, self.owner_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": repository_id})
        return record

    def _resolve_repository_root(self, destination: Path) -> Path:
        children = [child for child in destination.iterdir() if child.name != ".git"]
        if len(children) == 1 and children[0].is_dir() and not (destination / ".git").exists():
            return children[0]
        return destination

    def _validate_parsed_repository(self, total_files: int) -> None:
        if total_files == 0:
            raise ValidationServiceError("Repository archive does not contain any readable files.")

    def _repository_name_from_archive(self, filename: str) -> str:
        for suffix in (".tar.gz", ".tgz", ".zip", ".tar", ".gz"):
            if filename.lower().endswith(suffix):
                return filename[: -len(suffix)]
        return Path(filename).stem

    def _metadata_with_intelligence(self, meta, intelligence) -> dict:
        metadata = meta.model_dump(mode="json", by_alias=True)
        metadata["intelligence"] = intelligence.model_dump(mode="json", by_alias=True)
        return metadata

    def _git_revision(
        self,
        destination: Path,
        commit_sha: str | None,
        requested_ref: str | None,
    ) -> tuple[str, str, str]:
        """Return ``(kind, value, ref)`` for a GitHub import (RFC §3.2).

        New imports must always have both the immutable commit and the resolved
        ref. Missing legacy identity is handled only by the migration; silently
        creating a new repository without identity would violate RFC §3.2.
        """
        if not commit_sha or not GIT_SHA_RE.fullmatch(commit_sha):
            raise ServiceError("Unable to determine an immutable Git commit for the imported repository.")
        resolved_ref = self.github.read_head_ref(destination, requested_ref)
        if not resolved_ref or not resolved_ref.startswith("refs/"):
            raise ServiceError("Unable to determine the resolved Git ref for the imported repository.")
        return "git", commit_sha, resolved_ref

    def _content_hash_for_upload(self, archive_path: Path) -> str:
        digest = hashlib.sha256()
        with archive_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"
