import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.ai.orchestrator import AiOrchestrator
from app.ai.prompt_builder import PromptBuilder
from app.ai.providers.factory import ProviderFactory
from app.ai.providers.registry import ProviderRegistry
from app.ai.repository_context import RepositoryContextBuilder
from app.ai.types import AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import NotFoundError
from app.intelligence.query_service import (
    ProductSnapshotProjection,
    SnapshotDependencyDeclaration,
    SnapshotDependencyFact,
    SnapshotFileFact,
    SnapshotModuleFact,
)
from app.models.repository import RepositoryRecord
from app.schemas.ai import AiCitation, AiMessage, AiQueryRequest


def _record(root: Path) -> RepositoryRecord:
    return RepositoryRecord(
        id="repo-1",
        owner_id="owner-1",
        name="sample",
        source="upload",
        local_path=str(root),
        size=0,
        file_count=3,
        status="completed",
        analysis_stage="completed",
        analysis_progress=100,
        uploaded_at=datetime.now(UTC),
        analysed_at=datetime.now(UTC),
        repo_metadata={"intelligence": {"ignored": True}},
        file_tree=[],
        revision_kind="upload",
        revision_value="sha256:" + "a" * 64,
    )


def _projection(*, conflict: bool = False) -> ProductSnapshotProjection:
    declarations = (
        (
            SnapshotDependencyDeclaration(
                version="==2.31.0",
                dependency_type="production",
                manifest_path="requirements.txt",
                workspace_path=".",
                start_line=1,
                end_line=1,
                extractor="dependency-manifest",
                extractor_version="1",
            ),
            SnapshotDependencyDeclaration(
                version=">=2.32.0",
                dependency_type="production",
                manifest_path="requirements.txt",
                workspace_path=".",
                start_line=2,
                end_line=2,
                extractor="dependency-manifest",
                extractor_version="1",
            ),
        )
        if conflict
        else (
            SnapshotDependencyDeclaration(
                version="^18.0.0",
                dependency_type="production",
                manifest_path="package.json",
                workspace_path=".",
                start_line=1,
                end_line=1,
                extractor="dependency-manifest",
                extractor_version="1",
            ),
        )
    )
    dependency = SnapshotDependencyFact(
        stable_key="dep:pypi:requests" if conflict else "dep:npm:react",
        name="requests" if conflict else "react",
        ecosystem="pypi" if conflict else "npm",
        declarations=declarations,
    )
    return ProductSnapshotProjection(
        snapshot_id="snapshot-1",
        schema_version="ri.v1",
        repository_id="repo-1",
        revision_kind="upload",
        revision_value="sha256:" + "a" * 64,
        revision_ref=None,
        canonical_graph_hash="sha256:" + "b" * 64,
        primary_language="TypeScript",
        frameworks=() if conflict else ("React",),
        entry_points=("src/main.tsx",),
        modules=(SnapshotModuleFact(name="Services", role="service", paths=("src/services/user-service.ts",)),),
        files=(
            SnapshotFileFact("README.md", None, "documentation", "heuristic"),
            SnapshotFileFact("src/main.tsx", "typescript", "entrypoint", "heuristic"),
            SnapshotFileFact("src/services/user-service.ts", "typescript", "service", "heuristic"),
        ),
        dependencies=(dependency,),
        routes=(),
        diagnostics=(),
    )


class StaticSnapshots:
    def __init__(self, projection: ProductSnapshotProjection) -> None:
        self.projection = projection

    def product_projection(self, repository_id: str) -> ProductSnapshotProjection:
        assert repository_id == "repo-1"
        return self.projection


class StaticRepository:
    def __init__(self, record: RepositoryRecord) -> None:
        self.record = record

    def get_for_owner(self, repository_id: str, owner_id: str) -> RepositoryRecord | None:
        if repository_id != self.record.id or owner_id != self.record.owner_id:
            return None
        return self.record


class StaticConfigStore:
    def read_config(self) -> AiProviderConfig:
        return AiProviderConfig(provider="openai", api_key="key", model="test-model")


class FakeConversationRepository:
    """In-memory stand-in for ``AiConversationRepository`` in orchestrator tests."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str, list[dict] | None, datetime]] = []

    def append_turns(self, repository_id: str, owner_id: str, turns) -> None:
        for role, content, citations, created_at in turns:
            self.rows.append((repository_id, owner_id, role, content, citations, created_at))

    def list_conversation(self, repository_id: str, owner_id: str) -> list[AiMessage]:
        return [
            AiMessage(
                role=role,
                content=content,
                timestamp=created_at,
                citations=[AiCitation(**citation) for citation in citations] if citations else None,
            )
            for repo_id, owner, role, content, citations, created_at in self.rows
            if repo_id == repository_id and owner == owner_id
        ]


class FakeProvider:
    def __init__(self) -> None:
        self.prompt: PromptBundle | None = None

    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        self.prompt = prompt
        return AiProviderResponse(content=f"answer from {config.provider}")


def test_repository_context_builder_uses_sealed_snapshot(tmp_path: Path):
    record = _record(tmp_path)

    context = RepositoryContextBuilder(StaticSnapshots(_projection())).build(record)  # type: ignore[arg-type]

    assert context.repository.name == "sample"
    assert context.architecture.primary_language == "TypeScript"
    assert any(module.name == "Services" for module in context.architecture.modules)
    assert any(dependency.name == "react" for dependency in context.dependencies)
    assert context.selected_files
    # Citations are intentionally empty: the context has no source lines to ground
    # a real file:line citation, and placeholder citations were removed (F4/F5).
    assert context.citations == ()


def test_prompt_builder_preserves_existing_system_prompt_shape(tmp_path: Path):
    record = _record(tmp_path)
    context = RepositoryContextBuilder(StaticSnapshots(_projection())).build(record)  # type: ignore[arg-type]

    prompt = PromptBuilder().build(context, "What should I read first?")

    assert prompt.developer_prompt is None
    assert prompt.user_prompt == "What should I read first?"
    assert prompt.system_prompt.startswith("You are PARTHA's repository assistant for sample.")
    assert "Repository context:" in prompt.system_prompt
    assert "Primary language: TypeScript" in prompt.system_prompt
    assert "Files:" in prompt.system_prompt


def test_prompt_builder_renders_conflicting_declared_versions_without_none(tmp_path: Path):
    record = _record(tmp_path)

    context = RepositoryContextBuilder(StaticSnapshots(_projection(conflict=True))).build(record)  # type: ignore[arg-type]
    dependency = next(item for item in context.dependencies if item.name == "requests")
    prompt = PromptBuilder().build(context, "What dependencies conflict?")

    assert dependency.version is None
    assert dependency.declared_versions == ("==2.31.0", ">=2.32.0")
    assert dependency.has_version_conflict is True
    assert "- requests (conflicting declared versions: ==2.31.0, >=2.32.0)" in prompt.system_prompt
    assert "requests None" not in prompt.system_prompt


def test_provider_factory_resolves_registered_provider():
    provider = FakeProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)

    resolved = ProviderFactory(registry).resolve(AiProviderConfig(provider="openai", api_key="key"))

    assert resolved is provider


def test_ai_orchestrator_preserves_query_response_shape(tmp_path: Path):
    response, provider, _orchestrator = asyncio.run(_query_with_fake_provider(tmp_path))

    assert response.message.role == "assistant"
    assert response.message.content == "answer from openai"
    # No fabricated citations are returned (F4/F5); real ones await the graph (M2).
    assert response.message.citations is None
    assert response.suggestions == []
    assert provider.prompt is not None
    assert provider.prompt.user_prompt == "Explain this repo"


def test_ai_orchestrator_persists_both_turns_and_lists_them_back(tmp_path: Path):
    response, _provider, orchestrator = asyncio.run(_query_with_fake_provider(tmp_path))

    thread = orchestrator.list_conversation("repo-1")

    assert [message.role for message in thread] == ["user", "assistant"]
    assert thread[0].content == "Explain this repo"
    assert thread[1].content == response.message.content


def test_ai_orchestrator_list_conversation_404s_for_a_repository_the_caller_does_not_own(tmp_path: Path):
    record = _record(tmp_path)
    orchestrator = AiOrchestrator(
        repository=StaticRepository(record),  # type: ignore[arg-type]
        config_store=StaticConfigStore(),  # type: ignore[arg-type]
        context_builder=RepositoryContextBuilder(StaticSnapshots(_projection())),  # type: ignore[arg-type]
        prompt_builder=PromptBuilder(),
        provider_factory=ProviderFactory(ProviderRegistry()),
        conversation_repository=FakeConversationRepository(),
        owner_id="someone-else",
    )

    with pytest.raises(NotFoundError):
        orchestrator.list_conversation("repo-1")


async def _query_with_fake_provider(tmp_path: Path):
    record = _record(tmp_path)
    provider = FakeProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    orchestrator = AiOrchestrator(
        repository=StaticRepository(record),  # type: ignore[arg-type]
        config_store=StaticConfigStore(),  # type: ignore[arg-type]
        context_builder=RepositoryContextBuilder(StaticSnapshots(_projection())),  # type: ignore[arg-type]
        prompt_builder=PromptBuilder(),
        provider_factory=ProviderFactory(registry),
        conversation_repository=FakeConversationRepository(),
        owner_id="owner-1",
    )

    response = await orchestrator.query(AiQueryRequest(repository_id="repo-1", query="Explain this repo"))
    return response, provider, orchestrator
