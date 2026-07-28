"""Strict-loader tests: the real corpus loads, and every failure mode fails.

The happy-path assertions load the committed corpus through the real support
matrix. The failure-path assertions build deliberately broken manifests in a
temp directory and confirm the loader rejects each condition Issue #94 lists.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from app.extraction.support_matrix import CONSTRUCT_CAPABILITIES, MANIFEST_CAPABILITIES
from benchmark import paths
from benchmark.loader import (
    ManifestError,
    load_corpus,
    load_fixture,
    load_support_matrix,
    load_thresholds,
)

SUPPORT_MATRIX = load_support_matrix(paths.SUPPORT_MATRIX_PATH)


def test_committed_corpus_loads_cleanly():
    fixtures = load_corpus(paths.FIXTURES_DIR, SUPPORT_MATRIX)
    assert fixtures, "expected at least one committed fixture"
    ids = [fixture.fixture_id for fixture in fixtures]
    assert ids == sorted(ids), "fixtures must load in deterministic id order"
    assert len(ids) == len(set(ids)), "fixture ids must be unique"


def test_benchmark_mapping_is_complete_and_registry_authoritative():
    for capability in CONSTRUCT_CAPABILITIES:
        for benchmark_id in capability.benchmark_ids:
            assert benchmark_id in SUPPORT_MATRIX.constructs
            assert SUPPORT_MATRIX.constructs[benchmark_id].capability_id == capability.id
    for capability in MANIFEST_CAPABILITIES:
        assert capability.benchmark_disclosure


def test_thresholds_load_with_exact_fractions():
    thresholds = load_thresholds(paths.THRESHOLDS_PATH)
    assert thresholds.provenance_validity == 1
    assert thresholds.determinism == 1
    assert 0 < thresholds.precision <= 1
    assert 0 < thresholds.recall <= 1


def test_committed_recall_threshold_matches_precision_bar():
    """Issue #193: recall must not regress below the harmonized 0.95 bar.

    Recall started at a looser provisional 0.90 (Issue #94) while precision was
    already enforced at 0.95. Real extraction now clears 0.95 recall on the full
    corpus, so the acceptance bar is raised to match; this guards against a
    future PR quietly lowering it back without the Issue #94 sign-off the
    threshold file requires.
    """

    thresholds = load_thresholds(paths.THRESHOLDS_PATH)
    assert thresholds.precision >= Fraction(95, 100)
    assert thresholds.recall >= Fraction(95, 100)


def _base_manifest() -> dict:
    return {
        "schemaVersion": "ri-benchmark.v1",
        "fixtureId": "tmp-fixture",
        "fixtureClass": "minimal",
        "language": "python",
        "title": "t",
        "description": "d",
        "sourceRoot": ".",
        "revisionIdentity": "upload-sha256",
        "producerVersionSet": ["python-ast@1.0.0", "repository-inventory@1.1.0"],
        "constructsCovered": ["py.function.def"],
        "deterministic": False,
        "expected": {
            "nodes": [
                {
                    "nodeKind": "repository",
                    "stableKey": "repo:root",
                    "name": "repository",
                    "evidence": [
                        {
                            "path": "README.md",
                            "startLine": 1,
                            "endLine": 1,
                            "extractor": "repository-inventory",
                            "extractorVersion": "1.1.0",
                        }
                    ],
                },
                {
                    "nodeKind": "symbol",
                    "stableKey": "src/a.py::f",
                    "name": "f",
                    "language": "python",
                    "constructs": ["py.function.def"],
                    "evidence": [
                        {
                            "path": "src/a.py",
                            "startLine": 1,
                            "endLine": 1,
                            "extractor": "python-ast",
                            "extractorVersion": "1.0.0",
                        }
                    ],
                },
            ]
        },
    }


def _write_fixture(tmp_path: Path, manifest: dict, *, sources: dict[str, str] | None = None) -> Path:
    directory = tmp_path / "tmp-fixture"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    files = {"README.md": "# readme\n", "src/a.py": "def f():\n    return 1\n"}
    files.update(sources or {})
    for relative, content in files.items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return directory


def _load_bad(tmp_path: Path, mutate) -> None:
    manifest = _base_manifest()
    mutate(manifest)
    directory = _write_fixture(tmp_path, manifest)
    load_fixture(directory, SUPPORT_MATRIX)


def test_sanity_base_manifest_loads(tmp_path: Path):
    directory = _write_fixture(tmp_path, _base_manifest())
    fixture = load_fixture(directory, SUPPORT_MATRIX)
    assert fixture.fixture_id == "tmp-fixture"
    symbol = next(record.fact for record in fixture.expected if record.fact.subject == "src/a.py::f")
    assert symbol.name == "f"
    assert symbol.language == "python"


def test_source_policy_construct_cannot_bypass_fixture_language(tmp_path: Path):
    manifest = _base_manifest()
    manifest["constructsCovered"] = ["src.path_escape"]
    directory = _write_fixture(tmp_path, manifest)

    with pytest.raises(ManifestError, match="language mismatch"):
        load_fixture(directory, SUPPORT_MATRIX)


def test_manifest_synthetic_sources_are_deterministic_and_do_not_need_host_paths(tmp_path: Path):
    manifest = _base_manifest()
    manifest["syntheticFiles"] = {
        "z-last.txt": "last\n",
        "..\\escape.py": "def must_not_extract():\n    pass\n",
    }
    directory = _write_fixture(tmp_path, manifest)

    first = load_fixture(directory, SUPPORT_MATRIX)
    second = load_fixture(directory, SUPPORT_MATRIX)

    assert list(first.source_files()) == ["..\\escape.py", "README.md", "src/a.py", "z-last.txt"]
    assert first.source_files()["..\\escape.py"] == b"def must_not_extract():\n    pass\n"
    assert first.revision_value() == second.revision_value()


@pytest.mark.parametrize(
    "synthetic_files, message",
    [
        ([], "syntheticFiles must be an object"),
        ({"": "text"}, "synthetic source path must be a non-empty"),
        ({"README.md": "duplicate"}, "duplicates a stored file"),
        ({"src/synthetic.py": 7}, "must be UTF-8 text"),
    ],
)
def test_loader_rejects_invalid_synthetic_sources(tmp_path: Path, synthetic_files, message: str):
    manifest = _base_manifest()
    manifest["syntheticFiles"] = synthetic_files
    directory = _write_fixture(tmp_path, manifest)

    with pytest.raises(ManifestError, match=message):
        load_fixture(directory, SUPPORT_MATRIX)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda m: m.update(schemaVersion="ri-benchmark.v999"), "unsupported fixture schema version"),
        (lambda m: m.update(fixtureClass="weird"), "invalid fixtureClass"),
        (lambda m: m.update(language="cobol"), "unsupported language"),
        (lambda m: m.update(revisionIdentity="git-sha"), "unsupported revisionIdentity"),
        (lambda m: m.update(blessed=True), "forbidden key"),
        (lambda m: m.update(producerVersionSet=["badproducer"]), "must be 'name@version'"),
        (lambda m: m.update(constructsCovered=["py.not_a_construct"]), "undeclared benchmark construct"),
        (lambda m: m["expected"]["nodes"][1]["evidence"][0].update(path="/etc/passwd"), "absolute or escapes"),
        (lambda m: m["expected"]["nodes"][1]["evidence"][0].update(path="../escape.py"), "absolute or escapes"),
        (lambda m: m["expected"]["nodes"][1]["evidence"][0].update(startLine=0), "start_line must be >= 1"),
        (
            lambda m: m["expected"]["nodes"][1]["evidence"][0].update(startLine=2, endLine=1),
            "end_line must be >= start_line",
        ),
        (lambda m: m["expected"]["nodes"][1]["evidence"][0].update(endLine=999), "exceeds logical_line_count"),
        (lambda m: m["expected"]["nodes"][1]["evidence"][0].update(extractor="ghost"), "not in producerVersionSet"),
        (lambda m: m["expected"]["nodes"][1].__setitem__("evidence", []), "must carry >=1 evidence"),
        (lambda m: m["expected"]["nodes"][1].__setitem__("nodeKind", ""), "missing 'nodeKind'"),
        (lambda m: m["expected"]["nodes"].__setitem__(1, m["expected"]["nodes"][0]), "duplicate expected identity"),
    ],
)
def test_loader_rejects_bad_manifests(tmp_path: Path, mutate, message: str):
    with pytest.raises(ManifestError, match=message):
        _load_bad(tmp_path, mutate)


def test_missing_source_file_is_rejected(tmp_path: Path):
    manifest = _base_manifest()
    manifest["expected"]["nodes"][1]["evidence"][0]["path"] = "src/missing.py"
    directory = _write_fixture(tmp_path, manifest)
    with pytest.raises(ManifestError, match="missing source file"):
        load_fixture(directory, SUPPORT_MATRIX)


def test_duplicate_fixture_ids_across_corpus_are_rejected(tmp_path: Path):
    _write_fixture(tmp_path / "a", _base_manifest())
    second = tmp_path / "b" / "tmp-fixture"
    second.mkdir(parents=True)
    (second / "manifest.json").write_text(json.dumps(_base_manifest()), encoding="utf-8")
    (second / "README.md").write_text("# readme\n", encoding="utf-8")
    (second / "src").mkdir()
    (second / "src" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate fixture id"):
        load_corpus(tmp_path, SUPPORT_MATRIX)


def test_file_granularity_must_span_whole_file(tmp_path: Path):
    manifest = _base_manifest()
    manifest["expected"]["nodes"][1]["evidence"][0].update(granularity="file", startLine=1, endLine=1)
    directory = _write_fixture(tmp_path, manifest)  # src/a.py is 3 logical lines
    with pytest.raises(ManifestError, match="file-granularity evidence must span"):
        load_fixture(directory, SUPPORT_MATRIX)
