from datetime import UTC, datetime
from pathlib import Path

from app.analysis.architecture import ArchitectureAnalyzer
from app.graph.dependency_graph import DependencyGraphBuilder
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.parsers.repository_parser import RepositoryParser
from app.review.review_service import EngineeringReviewBuilder


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
        data_source="real",
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


def test_feature_consumers_read_repository_intelligence(tmp_path: Path):
    _sample_repository(tmp_path)
    _, _, _, intelligence = _build_intelligence(tmp_path)
    record = _record(tmp_path, intelligence)

    architecture = ArchitectureAnalyzer().build_architecture(record)
    dependencies = DependencyGraphBuilder().build(record)
    review = EngineeringReviewBuilder().build(record)

    assert architecture.summary.language == "TypeScript"
    assert any(node.id == "module:services" for node in architecture.nodes)
    assert any(node.name == "react" for node in dependencies.nodes)
    assert dependencies.vulnerability_assessment.status == "not_computed"
    assert dependencies.outdated_assessment.status == "not_computed"
    assert review.summary.total_findings >= 1
