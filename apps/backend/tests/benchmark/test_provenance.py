"""Provenance validator tests (RFC-0001 §6.2, Issue #94 §D)."""

from __future__ import annotations

from pathlib import Path

from benchmark import paths
from benchmark.facts import EvidenceSpan, Fact
from benchmark.loader import LoadedFixture, load_corpus, load_support_matrix
from benchmark.provenance import validate_expected, validate_fixture

SUPPORT_MATRIX = load_support_matrix(paths.SUPPORT_MATRIX_PATH)


def _fixture(directory: Path) -> LoadedFixture:
    return LoadedFixture(
        fixture_id="tmp",
        fixture_class="minimal",
        language="python",
        title="t",
        description="d",
        directory=directory,
        source_root=".",
        revision_identity="upload-sha256",
        producer_version_set=("python-ast@1.0.0",),
        constructs_covered=(),
        deterministic=False,
        expected=(),
    )


def _node(path: str, start: int, end: int, *, extractor: str = "python-ast", version: str = "1.0.0", granularity: str = "span") -> Fact:
    return Fact(
        fact_type="node",
        kind="symbol",
        subject=f"{path}::sym",
        truth_class="observed",
        evidence=(EvidenceSpan(path, start, end, extractor, version, granularity),),
    )


def test_committed_corpus_provenance_is_fully_valid():
    for fixture in load_corpus(paths.FIXTURES_DIR, SUPPORT_MATRIX):
        result = validate_expected(fixture)
        assert result.validity == 1, f"{fixture.fixture_id}: {[c.reason for c in result.invalid]}"


def test_valid_citation_passes(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")  # LLC = 3
    result = validate_fixture(_fixture(tmp_path), [_node("a.py", 1, 2)])
    assert result.validity == 1
    assert result.total == 1


def test_out_of_range_span_is_invalid(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")  # LLC = 2
    result = validate_fixture(_fixture(tmp_path), [_node("a.py", 1, 9)])
    assert result.validity == 0
    assert "outside 1..2" in result.invalid[0].reason


def test_missing_file_is_invalid(tmp_path: Path):
    result = validate_fixture(_fixture(tmp_path), [_node("ghost.py", 1, 1)])
    assert result.validity == 0
    assert "does not exist" in result.invalid[0].reason


def test_path_escape_is_invalid(tmp_path: Path):
    result = validate_fixture(_fixture(tmp_path), [_node("../secret.py", 1, 1)])
    assert result.validity == 0
    assert "escape" in result.invalid[0].reason


def test_binary_file_citation_is_invalid(tmp_path: Path):
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02data")
    result = validate_fixture(_fixture(tmp_path), [_node("blob.bin", 1, 1)])
    assert result.validity == 0
    assert "binary" in result.invalid[0].reason


def test_undeclared_producer_is_invalid(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    result = validate_fixture(_fixture(tmp_path), [_node("a.py", 1, 1, extractor="ghost")])
    assert result.validity == 0
    assert "undeclared producer" in result.invalid[0].reason


def test_no_citations_is_vacuously_valid(tmp_path: Path):
    assert validate_fixture(_fixture(tmp_path), []).validity == 1
