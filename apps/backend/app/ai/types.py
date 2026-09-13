from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.ai import AiCitation, AiProvider, AiProviderConfig

#: The model a provider starts on before anyone has fetched a list.
#:
#: A hardcoded default is a fact with a shelf life: `gemini-1.5-flash` was
#: correct when it was written and is not offered at all to a Google AI Studio
#: project created today, so every new user met "AI provider rejected the
#: request" with no way to discover what to type instead. These are kept
#: current, but the real answer to that problem is `providers/models.py`, which
#: asks the provider what this key can use -- a default is only ever the
#: starting point, never the only route to a working configuration.
DEFAULT_MODELS: dict[AiProvider, str] = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini": "gemini-2.5-flash",
    "openrouter": "openai/gpt-4.1-mini",
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
