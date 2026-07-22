import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.ai.orchestrator import AiOrchestrator
from app.ai.prompt_builder import PromptBuilder
from app.ai.providers.factory import ProviderFactory
from app.ai.providers.registry import ProviderRegistry
from app.ai.repository_context import RepositoryContextBuilder
from app.ai.types import AiProviderConfig, AiProviderResponse, PromptBundle
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.parsers.repository_parser import RepositoryParser
from app.schemas.ai import AiQueryRequest


def _sample_repository(root: Path) -> None:
    (root / "src" / "services").mkdir(parents=True)
    (root / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}', encoding="utf-8")
    (root / "src" / "main.tsx").write_text("import React from 'react';\nexport function App() { return null; }", encoding="utf-8")
    (root / "src" / "services" / "user-service.ts").write_text("export class UserService {}", encoding="utf-8")
    (root / "README.md").write_text("# Sample", encoding="utf-8")


def _record(root: Path) -> RepositoryRecord:
    tree, meta, total_size = RepositoryParser().parse(root)
    intelligence = RepositoryIntelligenceEngine().build("repo-1", "sample", root, tree, meta, total_size)
    metadata = intelligence.metadata.model_dump(mode="json", by_alias=True)
    metadata["intelligence"] = intelligence.model_dump(mode="json", by_alias=True)
    return RepositoryRecord(
        id="repo-1",
        owner_id="owner-1",
        name="sample",
        source="upload",
        local_path=str(root),
        size=total_size,
        file_count=meta.total_files,
        status="completed",
        data_source="real",
        analysis_stage="completed",
        analysis_progress=100,
        uploaded_at=datetime.now(UTC),
        analysed_at=datetime.now(UTC),
        repo_metadata=metadata,
        file_tree=[node.model_dump(mode="json", by_alias=True, exclude_none=True) for node in tree],
    )


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


class FakeProvider:
    def __init__(self) -> None:
        self.prompt: PromptBundle | None = None

    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        self.prompt = prompt
        return AiProviderResponse(content=f"answer from {config.provider}")


def test_repository_context_builder_uses_repository_intelligence(tmp_path: Path):
    _sample_repository(tmp_path)
    record = _record(tmp_path)

    context = RepositoryContextBuilder(RepositoryIntelligenceEngine()).build(record)

    assert context.repository.name == "sample"
    assert context.architecture.primary_language == "TypeScript"
    assert any(module.name == "Services" for module in context.architecture.modules)
    assert any(dependency.name == "react" for dependency in context.dependencies)
    assert context.selected_files
    # Citations are intentionally empty: the context has no source lines to ground
    # a real file:line citation, and placeholder citations were removed (F4/F5).
    assert context.citations == ()


def test_prompt_builder_preserves_existing_system_prompt_shape(tmp_path: Path):
    _sample_repository(tmp_path)
    record = _record(tmp_path)
    context = RepositoryContextBuilder(RepositoryIntelligenceEngine()).build(record)

    prompt = PromptBuilder().build(context, "What should I read first?")

    assert prompt.developer_prompt is None
    assert prompt.user_prompt == "What should I read first?"
    assert prompt.system_prompt.startswith("You are PARTHA's repository assistant for sample.")
    assert "Repository context:" in prompt.system_prompt
    assert "Primary language: TypeScript" in prompt.system_prompt
    assert "Files:" in prompt.system_prompt


def test_prompt_builder_renders_conflicting_declared_versions_without_none(tmp_path: Path):
    _sample_repository(tmp_path)
    (tmp_path / "requirements.txt").write_text(
        "requests==2.31.0\nrequests>=2.32.0\n", encoding="utf-8"
    )
    record = _record(tmp_path)

    context = RepositoryContextBuilder(RepositoryIntelligenceEngine()).build(record)
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
    response, provider = asyncio.run(_query_with_fake_provider(tmp_path))

    assert response.message.role == "assistant"
    assert response.message.content == "answer from openai"
    # No fabricated citations are returned (F4/F5); real ones await the graph (M2).
    assert response.message.citations is None
    assert response.suggestions == []
    assert provider.prompt is not None
    assert provider.prompt.user_prompt == "Explain this repo"


async def _query_with_fake_provider(tmp_path: Path):
    _sample_repository(tmp_path)
    record = _record(tmp_path)
    provider = FakeProvider()
    registry = ProviderRegistry()
    registry.register("openai", provider)
    orchestrator = AiOrchestrator(
        repository=StaticRepository(record),  # type: ignore[arg-type]
        config_store=StaticConfigStore(),  # type: ignore[arg-type]
        context_builder=RepositoryContextBuilder(RepositoryIntelligenceEngine()),
        prompt_builder=PromptBuilder(),
        provider_factory=ProviderFactory(registry),
        owner_id="owner-1",
    )

    response = await orchestrator.query(AiQueryRequest(repository_id="repo-1", query="Explain this repo"))
    return response, provider
