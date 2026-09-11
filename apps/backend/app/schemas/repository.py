from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl

from app.schemas.base import CamelModel

RepositorySource = Literal["upload", "github"]
RepositoryStatus = Literal["uploading", "analysing", "completed", "cancelled", "error"]
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
    """Import-time repository summary from RepositoryParser: file-tree counts plus
    filename/path heuristics for language, framework, entry point, package manager,
    and license. It is not a Repository Intelligence fact, carries no provenance, and
    can disagree with the sealed ri.v1 snapshot. Intelligence surfaces must read the
    snapshot query API instead. See docs/architecture/SYSTEM_OVERVIEW.md
    "Repository metadata vs. Repository Intelligence".
    """

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
    #: Repository-relative paths of symlinks that were recorded but never
    #: followed, so a reader can tell "not followed" from "not present".
    skipped_symlinks: list[str] = []


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


class RepositoryLineageEntry(CamelModel):
    """One repository row belonging to a lineage (#299, RFC-0002), or the
    lone entry for a standalone (unlineaged) repository."""

    repository_id: str
    sequence: int | None = None
    name: str
    status: RepositoryStatus
    revision: RepositoryRevision | None = None
    uploaded_at: datetime
    is_current: bool


class RepositoryLineageResponse(CamelModel):
    """History for the repository requested, most recent import first.

    An unlineaged repository (an upload, or a GitHub import whose ref never
    resolved -- RFC §4.3/§6) is never fabricated a lineage: ``is_lineaged`` is
    ``false``, ``lineage_id``/``canonical_source_key``/``canonical_branch``
    stay ``null``, and ``entries`` holds exactly the one requested repository.
    """

    is_lineaged: bool
    lineage_id: str | None = None
    canonical_source_key: str | None = None
    canonical_branch: str | None = None
    entries: list[RepositoryLineageEntry]


RepositoryReanalysisOutcome = Literal["already-current", "revision-imported"]


class RepositoryReanalysisResponse(CamelModel):
    """The answer to "has this repository moved?" (#448).

    ``already-current`` is a state, not a failure: the branch head still names
    the revision that is already sealed, so nothing was cloned and nothing was
    imported. ``repository`` is the lineage's latest revision either way --
    the newly imported one when the branch had moved, the existing one when it
    had not -- so a caller can render the result without a second request.

    ``remote_head`` is the commit the branch points at right now. On
    ``already-current`` it equals the sealed revision by definition; it is
    still returned so the client can show what was checked rather than asking
    the reader to trust that something was.
    """

    outcome: RepositoryReanalysisOutcome
    repository: RepositoryResponse
    remote_head: str
    #: The revision that was current before this call, present only when a new
    #: one was imported -- it is what a two-revision diff (#219) compares from.
    previous_repository_id: str | None = None
