from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import ConflictServiceError, NotFoundError, ValidationServiceError
from app.github.client import GitHubClient
from app.models.repository import RepositoryRecord
from app.parsers.repository_parser import RepositoryParser
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.repository import GitHubImportRequest, RepositoryListResponse, RepositoryResponse
from app.storage.local import LocalStorage


class RepositoryService:
    def __init__(
        self,
        repository: RepositoryRepository,
        storage: LocalStorage,
        github: GitHubClient,
        parser: RepositoryParser,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.github = github
        self.parser = parser
        self.settings = settings

    def list_repositories(self) -> RepositoryListResponse:
        records = self.repository.list()
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
        existing = self.repository.find_by_source(url, branch)
        if existing:
            raise ConflictServiceError(
                "Repository has already been imported.",
                {"repositoryId": existing.id, "name": existing.name},
            )

        destination = self.storage.reset_repository_path(repository_id)
        try:
            self.github.clone_public_repository(url, destination, branch)
            root = self._resolve_repository_root(destination)
            tree, meta, total_size = self.parser.parse(root)
            self._validate_parsed_repository(meta.total_files)
        except Exception:
            self.storage.delete_repository_id(repository_id)
            raise

        now = datetime.now(UTC)
        record = RepositoryRecord(
            id=repository_id,
            name=self.github.repository_name(url),
            description=None,
            source="github",
            source_url=url,
            branch=branch,
            local_path=str(root),
            size=total_size,
            file_count=meta.total_files,
            status="analysing",
            data_source="real",
            analysis_stage="building-file-tree",
            analysis_progress=70,
            uploaded_at=now,
            analysed_at=None,
            repo_metadata=meta.model_dump(mode="json", by_alias=True),
            file_tree=[node.model_dump(mode="json", by_alias=True, exclude_none=True) for node in tree],
        )
        return self.to_response(self.repository.add(record))

    async def import_uploaded_repository(self, file: UploadFile) -> RepositoryResponse:
        repository_id = str(uuid4())
        repository_name = self._repository_name_from_archive(file.filename or repository_id)
        existing = self.repository.find_by_name(repository_name)
        if existing:
            raise ConflictServiceError(
                "Repository has already been imported.",
                {"repositoryId": existing.id, "name": existing.name},
            )

        archive_path = await self.storage.save_upload(repository_id, file, self.settings.max_upload_size_bytes)
        try:
            root = self.storage.extract_archive(archive_path, repository_id)
            tree, meta, total_size = self.parser.parse(root)
            self._validate_parsed_repository(meta.total_files)
        except Exception:
            self.storage.delete_upload(archive_path)
            self.storage.delete_repository_id(repository_id)
            raise
        self.storage.delete_upload(archive_path)

        now = datetime.now(UTC)
        record = RepositoryRecord(
            id=repository_id,
            name=repository_name,
            description=None,
            source="upload",
            source_url=None,
            branch=None,
            local_path=str(root),
            size=total_size,
            file_count=meta.total_files,
            status="analysing",
            data_source="real",
            analysis_stage="building-file-tree",
            analysis_progress=70,
            uploaded_at=now,
            analysed_at=None,
            repo_metadata=meta.model_dump(mode="json", by_alias=True),
            file_tree=[node.model_dump(mode="json", by_alias=True, exclude_none=True) for node in tree],
        )
        return self.to_response(self.repository.add(record))

    def to_response(self, record: RepositoryRecord) -> RepositoryResponse:
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
            data_source=record.data_source,
            analysis_stage=record.analysis_stage,
            analysis_progress=record.analysis_progress,
            uploaded_at=record.uploaded_at,
            analysed_at=record.analysed_at,
            error_message=record.error_message,
            meta=record.repo_metadata,
            file_tree=record.file_tree,
        )

    def _get_record(self, repository_id: str) -> RepositoryRecord:
        record = self.repository.get(repository_id)
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
