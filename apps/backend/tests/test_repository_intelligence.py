from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.analysis.architecture import ArchitectureAnalyzer
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.parsers.repository_parser import RepositoryParser


def _sample_repository(root: Path) -> None:
    (root / "src" / "services").mkdir(parents=True)
    (root / "src" / "api").mkdir(parents=True)
    (root / "src" / "models").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "package.json").write_text(
        '{"dependencies":{"react":"^18.0.0","@tanstack/react-query":"^5.0.0"},"devDependencies":{"vite":"^5.0.0"}}',
        encoding="utf-8",
    )
    (root / "src" / "main.tsx").write_text("import React from 'react';\nexport function App() { return null; }", encoding="utf-8")
    (root / "src" / "api" / "routes.ts").write_text(
        "import { UserService } from '../services/user-service';\nrouter.get('/users', handler);\nexport const routes = [];",
        encoding="utf-8",
    )
    (root / "src" / "services" / "user-service.ts").write_text(
        "import { User } from '../models/user';\nexport class UserService { list() { return []; } }",
        encoding="utf-8",
    )
    (root / "src" / "models" / "user.ts").write_text("export interface User { id: string }", encoding="utf-8")
    (root / "tests" / "user-service.test.ts").write_text("export const ok = true;", encoding="utf-8")
    (root / ".github" / "workflows" / "ci.yml").write_text("name: CI", encoding="utf-8")
    (root / "README.md").write_text("# Sample", encoding="utf-8")
    (root / "LICENSE").write_text("Apache License\nVersion 2.0", encoding="utf-8")


def _build_intelligence(root: Path):
    tree, meta, total_size = RepositoryParser().parse(root)
    return tree, meta, total_size, RepositoryIntelligenceEngine().build("repo-1", "sample", root, tree, meta, total_size)


def _record(root: Path, intelligence) -> RepositoryRecord:
    metadata = intelligence.metadata.model_dump(mode="json", by_alias=True)
    metadata["intelligence"] = intelligence.model_dump(mode="json", by_alias=True)
    return RepositoryRecord(
        id="repo-1",
        name="sample",
        source="upload",
        local_path=str(root),
        size=intelligence.discovery.statistics.total_size,
        file_count=intelligence.discovery.statistics.total_files,
        status="completed",
        analysis_stage="completed",
        analysis_progress=100,
        uploaded_at=datetime.now(UTC),
        analysed_at=datetime.now(UTC),
        repo_metadata=metadata,
        file_tree=[],
    )


def test_repository_intelligence_detects_discovery_and_source_code(tmp_path: Path):
    _sample_repository(tmp_path)
    _, _, _, intelligence = _build_intelligence(tmp_path)

    assert intelligence.discovery.primary_language == "TypeScript"
    assert "React" in intelligence.discovery.frameworks
    assert "npm" in intelligence.discovery.package_managers
    assert "Vite" in intelligence.discovery.build_systems
    assert intelligence.discovery.ci_files == [".github/workflows/ci.yml"]
    assert intelligence.discovery.statistics.test_files == 1
    assert any(module.id == "module:services" for module in intelligence.modules)
    assert any(file.role == "route" and "/users" in file.api_routes for file in intelligence.files)
    assert any(symbol.name == "UserService" and symbol.kind == "class" for symbol in intelligence.symbols)
    assert any(dependency.name == "react" for dependency in intelligence.dependencies)
    assert any(relationship.type == "contains" for relationship in intelligence.graph.relationships)
    assert any(relationship.type == "imports" for relationship in intelligence.graph.relationships)
    assert any(relationship.type == "depends_on" for relationship in intelligence.graph.relationships)


def test_repository_intelligence_checks_cancellation_between_files(
    tmp_path: Path,
    monkeypatch,
):
    _sample_repository(tmp_path)
    tree, metadata, total_size = RepositoryParser().parse(tmp_path)
    engine = RepositoryIntelligenceEngine()
    processed: list[str] = []
    original_file_intelligence = engine._file_intelligence

    def _file_intelligence(root, node):
        processed.append(node.path)
        return original_file_intelligence(root, node)

    def _check_cancelled():
        if processed:
            raise RuntimeError("cancelled")

    monkeypatch.setattr(engine, "_file_intelligence", _file_intelligence)

    with pytest.raises(RuntimeError, match="cancelled"):
        engine.build(
            "repo-1",
            "sample",
            tmp_path,
            tree,
            metadata,
            total_size,
            check_cancelled=_check_cancelled,
        )

    assert len(processed) == 1


def test_repository_intelligence_is_serializable_and_persisted(tmp_path: Path):
    _sample_repository(tmp_path)
    _, _, _, intelligence = _build_intelligence(tmp_path)
    record = _record(tmp_path, intelligence)
    engine = RepositoryIntelligenceEngine()

    loaded = engine.load(record)

    assert loaded is not None
    assert loaded.repository_id == "repo-1"
    assert loaded.graph.nodes
    assert loaded.model_dump(mode="json", by_alias=True)["graph"]["nodes"]


def test_architecture_without_snapshot_reports_honest_unknown_state(tmp_path: Path):
    """Architecture (#95) reads exclusively through the snapshot query layer; it
    no longer reads ``repo_metadata['intelligence']``. Without a sealed ri.v1
    snapshot it reports an honest "unknown" state instead of falling back to
    the legacy blob that the dependency preview still reads."""

    _sample_repository(tmp_path)
    _, _, _, intelligence = _build_intelligence(tmp_path)
    record = _record(tmp_path, intelligence)

    architecture = ArchitectureAnalyzer().build_architecture(record)

    assert architecture.summary.language == "Unknown"
    assert any(node.id == "module:repository" for node in architecture.nodes)


def _nested_manifest_repository(root: Path) -> None:
    (root / "apps" / "frontend").mkdir(parents=True)
    (root / "apps" / "backend").mkdir(parents=True)
    (root / "services" / "worker").mkdir(parents=True)
    (root / "node_modules" / "hidden").mkdir(parents=True)
    (root / ".venv" / "hidden").mkdir(parents=True)
    (root / "dist" / "hidden").mkdir(parents=True)
    (root / "build" / "hidden").mkdir(parents=True)
    (root / ".next" / "hidden").mkdir(parents=True)
    (root / ".cache" / "hidden").mkdir(parents=True)
    (root / "vendor" / "hidden").mkdir(parents=True)
    (root / "apps" / "frontend" / "package.json").write_text(
        '''{
  "dependencies": {
    "react": "^18.3.0",
    "shared-npm": "^1.0.0"
  }
}
''',
        encoding="utf-8",
    )
    (root / "apps" / "backend" / "pyproject.toml").write_text(
        '''[project]
dependencies = [
  "fastapi>=0.115",
  "requests==2.31.0",
]
''',
        encoding="utf-8",
    )
    (root / "services" / "worker" / "requirements.txt").write_text(
        "requests>=2.32\ncelery==5.4\n", encoding="utf-8"
    )
    for directory in ("node_modules", ".venv", "dist", "build", ".next", ".cache", "vendor"):
        (root / directory / "hidden" / "package.json").write_text(
            '{"dependencies":{"not-visible":"1"}}', encoding="utf-8"
        )


def test_nested_workspace_manifest_inventory_preserves_all_declarations_and_graph_evidence(tmp_path: Path):
    _nested_manifest_repository(tmp_path)
    tree, metadata, total_size = RepositoryParser().parse(tmp_path)
    engine = RepositoryIntelligenceEngine()
    intelligence = engine.build("repo-nested", "nested", tmp_path, tree, metadata, total_size)

    dependencies = {dependency.id: dependency for dependency in intelligence.dependencies}
    assert set(dependencies) == {
        "dependency:npm:react",
        "dependency:npm:shared-npm",
        "dependency:pypi:celery",
        "dependency:pypi:fastapi",
        "dependency:pypi:requests",
    }
    assert intelligence.dependency_manifest_count == 3
    assert intelligence.dependency_diagnostics == []

    react = dependencies["dependency:npm:react"]
    assert react.version == "^18.3.0"
    assert react.declarations[0].manifest_path == "apps/frontend/package.json"
    assert react.declarations[0].workspace_path == "apps/frontend"
    assert react.declarations[0].start_line == 3
    assert react.declarations[0].extractor == "dependency-manifest"
    assert react.declarations[0].extractor_version == "1.2.0"

    fastapi = dependencies["dependency:pypi:fastapi"]
    assert fastapi.declarations[0].manifest_path == "apps/backend/pyproject.toml"
    assert fastapi.declarations[0].start_line == 3
    assert fastapi.declarations[0].version == ">=0.115"

    requests = dependencies["dependency:pypi:requests"]
    assert requests.version is None  # conflicting declarations are not overwritten
    assert [
        (item.manifest_path, item.version, item.start_line)
        for item in requests.declarations
    ] == [
        ("apps/backend/pyproject.toml", "==2.31.0", 4),
        ("services/worker/requirements.txt", ">=2.32", 1),
    ]
    requests_edge = next(
        edge
        for edge in intelligence.graph.relationships
        if edge.type == "depends_on" and edge.target == requests.id
    )
    assert requests_edge.evidence == [
        "apps/backend/pyproject.toml",
        "services/worker/requirements.txt",
    ]
    assert all("not-visible" not in dependency.name for dependency in intelligence.dependencies)

    flattened = engine._flatten_files(tree)
    first = engine._dependencies(tmp_path, flattened)
    second = engine._dependencies(tmp_path, list(reversed(flattened)))
    assert first == second


def test_nested_malformed_manifests_are_diagnostic_without_erasing_valid_declarations(tmp_path: Path):
    (tmp_path / "apps" / "valid").mkdir(parents=True)
    (tmp_path / "apps" / "broken-json").mkdir(parents=True)
    (tmp_path / "apps" / "broken-toml").mkdir(parents=True)
    (tmp_path / "apps" / "valid" / "requirements.txt").write_text("httpx>=0.27\n", encoding="utf-8")
    (tmp_path / "apps" / "broken-json" / "package.json").write_text("{", encoding="utf-8")
    (tmp_path / "apps" / "broken-toml" / "pyproject.toml").write_text("[project\ndependencies = [", encoding="utf-8")

    tree, metadata, total_size = RepositoryParser().parse(tmp_path)
    intelligence = RepositoryIntelligenceEngine().build("repo-malformed", "malformed", tmp_path, tree, metadata, total_size)

    assert [dependency.name for dependency in intelligence.dependencies] == ["httpx"]
    assert intelligence.dependency_manifest_count == 3
    assert [
        (diagnostic.code, diagnostic.path, diagnostic.producer)
        for diagnostic in intelligence.dependency_diagnostics
    ] == [
        ("RI-SRC-MALFORMED", "apps/broken-json/package.json", "dependency-manifest@1.2.0"),
        ("RI-SRC-MALFORMED", "apps/broken-toml/pyproject.toml", "dependency-manifest@1.2.0"),
    ]


def test_empty_valid_manifest_is_distinct_from_a_malformed_manifest(tmp_path: Path):
    (tmp_path / "apps" / "empty").mkdir(parents=True)
    (tmp_path / "apps" / "broken").mkdir(parents=True)
    (tmp_path / "apps" / "empty" / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "apps" / "broken" / "package.json").write_text("{", encoding="utf-8")

    tree, metadata, total_size = RepositoryParser().parse(tmp_path)
    intelligence = RepositoryIntelligenceEngine().build("repo-empty", "empty", tmp_path, tree, metadata, total_size)

    assert intelligence.dependency_manifest_count == 2
    assert intelligence.dependencies == []
    assert [(item.code, item.path) for item in intelligence.dependency_diagnostics] == [
        ("RI-SRC-MALFORMED", "apps/broken/package.json")
    ]


def test_oversized_manifest_is_skipped_before_an_unbounded_read(tmp_path: Path, monkeypatch):
    package_json = tmp_path / "apps" / "large" / "package.json"
    package_json.parent.mkdir(parents=True)
    package_json.write_bytes(b" " * (512 * 1024 + 1))

    def unexpected_read_bytes(_: Path) -> bytes:
        raise AssertionError("manifest candidates must not be loaded with read_bytes")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read_bytes)
    tree, metadata, total_size = RepositoryParser().parse(tmp_path)
    intelligence = RepositoryIntelligenceEngine().build("repo-large", "large", tmp_path, tree, metadata, total_size)

    assert intelligence.dependency_manifest_count == 1
    assert intelligence.dependencies == []
    assert [(item.code, item.path, item.details) for item in intelligence.dependency_diagnostics] == [
        (
            "RI-LIMIT-SKIP",
            "apps/large/package.json",
            {"budgetBytes": 512 * 1024, "reportedBytes": 512 * 1024 + 1},
        )
    ]


def test_requirements_url_fragments_remain_distinct_during_aggregation(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "example @ https://host.example/archive.whl#sha256=first\n"
        "example @ https://host.example/archive.whl#sha256=second\n",
        encoding="utf-8",
    )
    tree, metadata, total_size = RepositoryParser().parse(tmp_path)
    intelligence = RepositoryIntelligenceEngine().build("repo-fragments", "fragments", tmp_path, tree, metadata, total_size)

    dependency = intelligence.dependencies[0]
    assert dependency.name == "example"
    assert dependency.version is None
    assert [item.version for item in dependency.declarations] == [
        "@ https://host.example/archive.whl#sha256=first",
        "@ https://host.example/archive.whl#sha256=second",
    ]
