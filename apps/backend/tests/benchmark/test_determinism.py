"""Determinism harness tests: real SnapshotStore + canonical hash (Issue #94 §E)."""

from __future__ import annotations

from pathlib import Path

from benchmark import determinism, paths
from benchmark.loader import load_corpus, load_support_matrix

SUPPORT_MATRIX = load_support_matrix(paths.SUPPORT_MATRIX_PATH)


def _deterministic_fixtures():
    return [f for f in load_corpus(paths.FIXTURES_DIR, SUPPORT_MATRIX) if f.deterministic]


def test_deterministic_fixtures_seal_to_a_stable_hash(tmp_path: Path):
    fixtures = _deterministic_fixtures()
    assert fixtures, "expected at least one deterministic fixture in the corpus"
    for index, fixture in enumerate(fixtures):
        result = determinism.check_fixture(fixture, tmp_path / f"det-{index}.db")
        assert result.deterministic, (
            f"{fixture.fixture_id}: sealed {result.sealed_hash_a} vs {result.sealed_hash_b}; "
            f"pure {result.pure_hash_a} vs {result.pure_hash_b}"
        )
        assert result.sealed_hash_a.startswith("sha256:")


def test_sealed_and_pure_hash_agree_for_the_same_graph(tmp_path: Path):
    # The real SnapshotStore seal and the pure canonical hash are the same
    # function over the same node graph, so they must produce identical digests.
    fixture = _deterministic_fixtures()[0]
    result = determinism.check_fixture(fixture, tmp_path / "agree.db")
    assert result.sealed_hash_a == result.pure_hash_a
