from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.ai import AiCitation, AiProvider, AiProviderConfig

DEFAULT_MODELS: dict[AiProvider, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
}


@dataclass(frozen=True)
class Citation:
    file: str
    start_line: int = 1
    end_line: int = 1
    content: str = ""

    def to_schema(self) -> AiCitation:
        return AiCitation(
            file=self.file,
            start_line=self.start_line,
            end_line=self.end_line,
            content=self.content,
        )


@dataclass(frozen=True)
class RepositoryIdentity:
    id: str
    name: str


@dataclass(frozen=True)
class SnapshotIdentity:
    id: str
    schema_version: str
    revision_kind: str
    revision_value: str


@dataclass(frozen=True)
class ModuleContext:
    name: str
    role: str
    file_count: int


@dataclass(frozen=True)
class ArchitectureContext:
    primary_language: str
    frameworks: tuple[str, ...]
    entry_points: tuple[str, ...]
    modules: tuple[ModuleContext, ...]


@dataclass(frozen=True)
class DependencyContext:
    name: str
    version: str | None
    declared_versions: tuple[str | None, ...]
    has_version_conflict: bool


@dataclass(frozen=True)
class DocumentationContext:
    files: tuple[str, ...]


@dataclass(frozen=True)
class EngineeringReviewContext:
    findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelectedFileContext:
    path: str


@dataclass(frozen=True)
class RepositoryContext:
    repository: RepositoryIdentity
    snapshot: SnapshotIdentity
    architecture: ArchitectureContext
    dependencies: tuple[DependencyContext, ...]
    documentation: DocumentationContext
    engineering_review: EngineeringReviewContext
    selected_files: tuple[SelectedFileContext, ...]
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str
    developer_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AiProviderResponse:
    content: str
