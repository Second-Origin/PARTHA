"""Regression guard for Issue #171's single sealed product read model."""

import ast
from pathlib import Path


PRODUCT_ROOT = Path(__file__).parents[1] / "app"
EXCLUDED = {
    PRODUCT_ROOT / "intelligence" / "engine.py",
    PRODUCT_ROOT / "intelligence" / "__init__.py",
}


def test_product_code_has_no_legacy_intelligence_read_path():
    violations: list[str] = []
    for path in sorted(PRODUCT_ROOT.rglob("*.py")):
        if path in EXCLUDED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.intelligence.engine":
                violations.append(f"{path.relative_to(PRODUCT_ROOT)}:{node.lineno}: imports legacy engine")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "RepositoryIntelligenceEngine":
                    violations.append(f"{path.relative_to(PRODUCT_ROOT)}:{node.lineno}: constructs legacy engine")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"load", "from_record"}:
                    violations.append(f"{path.relative_to(PRODUCT_ROOT)}:{node.lineno}: calls {node.func.attr}()")
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "repo_metadata"
                and isinstance(node.slice, ast.Constant)
                and node.slice.value == "intelligence"
            ):
                violations.append(
                    f"{path.relative_to(PRODUCT_ROOT)}:{node.lineno}: reads repo_metadata['intelligence']"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "repo_metadata"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "intelligence"
            ):
                violations.append(
                    f"{path.relative_to(PRODUCT_ROOT)}:{node.lineno}: reads repo_metadata.get('intelligence')"
                )
    assert violations == []


#: Analytical consumers per AGENTS.md's canonical-boundary rule: architecture,
#: dependencies, review, insights, AI and exports. `app/services` and
#: `app/workers` are deliberately excluded -- they legitimately read/write
#: `record.file_tree` as part of ingestion (populating the field the sealed
#: snapshot is built from), not as a canonical-source bypass.
ANALYTICAL_CONSUMER_DIRS = ("analysis", "graph", "review", "insights", "ai", "reports")


def test_analytical_consumers_never_read_repository_file_tree():
    """Regression guard for Issue #217: no analytical consumer may derive its
    output from ``RepositoryRecord.file_tree`` -- a sealed ``ri.v1`` snapshot,
    or an explicit missing-snapshot state, is the only allowed source."""

    violations: list[str] = []
    for consumer_dir in ANALYTICAL_CONSUMER_DIRS:
        for path in sorted((PRODUCT_ROOT / consumer_dir).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "file_tree":
                    violations.append(f"{path.relative_to(PRODUCT_ROOT)}:{node.lineno}: reads .file_tree")
    assert violations == []
