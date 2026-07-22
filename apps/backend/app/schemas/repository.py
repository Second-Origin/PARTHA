from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl

from app.schemas.base import CamelModel

RepositorySource = Literal["upload", "github"]
RepositoryStatus = Literal["uploading", "analysing", "completed", "error"]
AnalysisStage = Literal[
    "uploading",
    "extracting",
    "reading-structure",
    "detecting-languages",
    "detecting-framework",
    "building-file-tree",
    "extracting-modules",
    "building-dependency-graph",
    "preparing-architecture",
    "completed",
]


class FileTreeNode(CamelModel):
    id: str
    name: str
    type: Literal["file", "folder"]
    path: str
    children: list["FileTreeNode"] | None = None
    size: int | None = None
    extension: str | None = None
    language: str | None = None


class RepositoryMeta(CamelModel):
    language: str
    framework: str
    total_files: int
    total_folders: int
    entry_point: str | None
    config_files: list[str]
    package_manager: str | None
    has_readme: bool
    has_license: bool
    license_name: str | None


class RepositoryRevision(CamelModel):
    """First-class repository revision identity (#87, RFC §3.2).

    ``value`` is the immutable identity: a 40-char lowercase git commit SHA for
    GitHub imports, or a ``sha256:<hex>`` archive content hash for uploads.
    ``ref`` (e.g. ``refs/heads/main``) is a moving pointer — descriptive
    metadata only, never identity, and always ``null`` for uploads.
    """

    kind: Literal["git", "upload"]
    value: str
    ref: str | None = None


class RepositoryResponse(CamelModel):
    id: str
    name: str
    description: str | None = None
    source: RepositorySource
    source_url: str | None = None
    branch: str | None = None
    size: int
    file_count: int
    status: RepositoryStatus
    analysis_stage: AnalysisStage | None = None
    analysis_progress: int
    uploaded_at: datetime
    analysed_at: datetime | None = None
    error_message: str | None = None
    # First-class revision identity, sourced from indexed immutable columns and
    # no longer from the mutable ``repo_metadata`` blob (#87). ``commit_sha`` is
    # retained as a backward-compatible alias of ``revision.value``.
    revision: RepositoryRevision | None = None
    commit_sha: str | None = None
    meta: RepositoryMeta | None = None
    file_tree: list[FileTreeNode] = Field(default_factory=list)


class GitHubImportRequest(CamelModel):
    url: HttpUrl
    branch: str | None = None


class RepositoryListResponse(CamelModel):
    data: list[RepositoryResponse]
    total: int


class RepositoryFileResponse(CamelModel):
    path: str
    content: str
    size: int
    truncated: bool = False
    is_binary: bool = False
    is_image: bool = False
    media_type: str | None = None
