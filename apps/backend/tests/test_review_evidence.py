from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.intelligence.engine import RepositoryIntelligenceEngine
from app.intelligence.models import SourceFileIntelligence
from app.models.repository import RepositoryRecord
from app.parsers.repository_parser import RepositoryParser
from app.review.review_service import (
    LARGE_FILE_BYTES,
    EngineeringReviewBuilder,
    _is_refactorable_source_file,
)

_OLD_PLACEHOLDER_IMPACT = "This can reduce maintainability, correctness, or operational confidence."


def _repository_with_gaps(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}', encoding="utf-8")
    (root / "src" / "main.tsx").write_text("import React from 'react';\nexport function App() { return null; }", encoding="utf-8")
    (root / "src" / "big.ts").write_text("export const value = 1;\n" * 3000, encoding="utf-8")  # > 40 KB
    (root / ".env").write_text("API_SECRET=super-secret\n", encoding="utf-8")
    # Deliberately no README, LICENSE, tests, or CI workflow.


def _review(root: Path):
    tree, meta, total_size = RepositoryParser().parse(root)
    intelligence = RepositoryIntelligenceEngine().build("repo-1", "sample", root, tree, meta, total_size)
    metadata = intelligence.metadata.model_dump(mode="json", by_alias=True)
    metadata["intelligence"] = intelligence.model_dump(mode="json", by_alias=True)
    record = RepositoryRecord(
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
    return EngineeringReviewBuilder().build(record)


def test_findings_carry_specific_impact_and_evidence(tmp_path: Path):
    _repository_with_gaps(tmp_path)
    review = _review(tmp_path)
    findings = {finding.id: finding for finding in review.findings}

    # No finding should reuse the old constant placeholder impact.
    assert all(finding.impact != _OLD_PLACEHOLDER_IMPACT for finding in review.findings)
    # Problem text is finding-specific, not a copy of the title.
    assert all(finding.problem != finding.title for finding in review.findings)

    # Real, file-level evidence is attached where it exists.
    assert ".env" in findings["env-file-present"].affected_files
    assert findings["large-files"].affected_files
    assert any("big.ts" in path for path in findings["large-files"].affected_files)


def test_roadmap_is_derived_from_findings(tmp_path: Path):
    _repository_with_gaps(tmp_path)
    review = _review(tmp_path)

    finding_ids = {finding.id for finding in review.findings}
    assert len(review.roadmap) >= 2  # not the single hardcoded step
    for step in review.roadmap:
        assert step.related_findings  # each step links back to real findings
        assert set(step.related_findings) <= finding_ids


@pytest.mark.parametrize(
    ("path", "extension", "role", "expected"),
    [
        ("package-lock.json", "json", "unknown", False),
        ("poetry.lock", "lock", "unknown", False),
        ("vendor/runtime.ts", "ts", "unknown", False),
        ("src/generated/client.ts", "ts", "unknown", False),
        ("src/client.generated.ts", "ts", "unknown", False),
        ("src/bundle.min.js", "js", "unknown", False),
        ("src/views.g.cs", "cs", "unknown", False),
        ("api/service.pb.go", "go", "unknown", False),
        ("rpc/service_pb2_grpc.py", "py", "unknown", False),
        ("bin/tool.cs", "cs", "unknown", False),
        ("build/application.ts", "ts", "unknown", False),
        ("obj/views.cs", "cs", "unknown", False),
        ("obj/views.g.cs", "cs", "unknown", False),
        ("vite.config.ts", "ts", "configuration", False),
        ("webpack.config.ts", "ts", "unknown", False),
        ("src/application.ts", "ts", "service", True),
    ],
)
def test_large_file_rule_only_accepts_refactorable_authored_source(
    path: str,
    extension: str,
    role: str,
    expected: bool,
):
    file = SourceFileIntelligence(
        path=path,
        name=path.rsplit("/", 1)[-1],
        module_id="module:source",
        extension=extension,
        size=LARGE_FILE_BYTES + 1,
        role=role,  # type: ignore[arg-type]
    )

    assert _is_refactorable_source_file(file) is expected


def test_large_file_finding_excludes_artifacts_and_includes_measured_source_size(tmp_path: Path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    authored_source = "export const value = 1;\n" * 3_000
    lockfile = '{"lockfileVersion": 3}\n' * 3_000
    (source_dir / "application.ts").write_bytes(authored_source.encode("utf-8"))
    (tmp_path / "package-lock.json").write_bytes(lockfile.encode("utf-8"))

    review = _review(tmp_path)
    finding = next(finding for finding in review.findings if finding.id == "large-files")

    expected_path = next(path for path in finding.affected_files if path.endswith("src/application.ts"))
    assert finding.affected_files == [expected_path]
    expected_details = [(expected_path, len(authored_source.encode("utf-8")))]
    assert [(detail.path, detail.size_bytes) for detail in finding.affected_file_details] == expected_details
    assert finding.model_dump(by_alias=True)["affectedFileDetails"] == [
        {"path": path, "sizeBytes": size} for path, size in expected_details
    ]
    copy = " ".join((finding.problem, finding.impact, finding.recommendation)).lower()
    assert "review signal" in copy
    assert "low cohesion" not in copy
    assert "god-file" not in copy
