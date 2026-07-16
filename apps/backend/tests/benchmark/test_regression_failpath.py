"""The benchmark's failure path really fails (Issue #94 §F).

A regression guard is worthless if it only proves the happy path. These tests
inject deliberately wrong extractor output, invalid citations, a broken manifest,
and a determinism break, and assert the runner reports a failure and a non-zero
exit code in every case. They also prove a *good* extractor passes — so the gate
is discriminating, not just always-red.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark import determinism as determinism_module
from benchmark import runner
from benchmark.determinism import DeterminismResult
from benchmark.facts import EvidenceSpan, Fact
from benchmark.loader import LoadedFixture


class PerfectAdapter:
    """A hypothetical extractor that emits exactly the golden facts."""

    name = "perfect"
    available = True

    def extract(self, fixture: LoadedFixture) -> list[Fact]:
        return [record.fact for record in fixture.expected]


class SilentAdapter:
    """An extractor that emits nothing: every expected fact becomes a miss."""

    name = "silent"
    available = True

    def extract(self, fixture: LoadedFixture) -> list[Fact]:
        return []


class InventingAdapter:
    """An extractor that only invents facts: all false positives, zero recall."""

    name = "inventing"
    available = True

    def extract(self, fixture: LoadedFixture) -> list[Fact]:
        ghosts: list[Fact] = []
        for record in fixture.expected:
            if record.fact.evidence:
                span = record.fact.evidence[0]
                ghosts.append(
                    Fact(fact_type="node", kind="symbol", subject=f"{span.path}::ghost",
                         truth_class="observed", evidence=(span,))
                )
        return ghosts


class BadCitationAdapter:
    """A near-perfect extractor whose one emitted citation is out of range."""

    name = "bad-citation"
    available = True

    def extract(self, fixture: LoadedFixture) -> list[Fact]:
        facts = [record.fact for record in fixture.expected]
        for index, fact in enumerate(facts):
            if fact.evidence:
                span = fact.evidence[0]
                broken = EvidenceSpan(span.path, span.start_line, 99999, span.extractor, span.extractor_version, span.granularity)
                facts[index] = Fact(
                    fact_type=fact.fact_type, kind=fact.kind, subject=fact.subject, object=fact.object,
                    predicate=fact.predicate, referent=fact.referent, truth_class=fact.truth_class,
                    value=fact.value, severity=fact.severity, producer=fact.producer, evidence=(broken,),
                )
                break
        return facts


def test_a_perfect_extractor_passes_scoring():
    result = runner.run(adapter=PerfectAdapter())
    assert not result.scoring.deferred
    assert result.scoring.report is not None
    assert result.scoring.report.overall.precision == 1
    assert result.scoring.report.overall.recall == 1
    assert result.passed and result.exit_code == 0


def test_a_silent_extractor_fails_the_recall_gate():
    result = runner.run(adapter=SilentAdapter())
    assert result.scoring.report is not None
    assert result.scoring.report.overall.recall < result.thresholds.recall
    assert not result.passed
    assert result.exit_code == 1


def test_an_inventing_extractor_fails_the_precision_gate():
    result = runner.run(adapter=InventingAdapter())
    assert result.scoring.report is not None
    assert result.scoring.report.overall.precision < result.thresholds.precision
    assert not result.passed
    assert result.exit_code == 1


def test_an_invalid_emitted_citation_fails_even_if_scoring_is_high():
    result = runner.run(adapter=BadCitationAdapter())
    assert result.scoring.actual_provenance is not None
    assert result.scoring.actual_provenance.validity < 1
    assert not result.passed
    assert result.exit_code == 1


def test_a_broken_manifest_fails_the_build(tmp_path: Path):
    fixture_dir = tmp_path / "broken"
    fixture_dir.mkdir()
    (fixture_dir / "manifest.json").write_text(json.dumps({"schemaVersion": "ri-benchmark.v999"}), encoding="utf-8")
    result = runner.run(fixtures_dir=tmp_path)
    assert result.load_error is not None
    assert not result.passed
    assert result.exit_code == 1


def test_a_determinism_break_fails_the_build(monkeypatch):
    def fake_check(fixture, db_path):
        return DeterminismResult(fixture.fixture_id, "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                 "sha256:" + "a" * 64, "sha256:" + "a" * 64)

    monkeypatch.setattr(runner, "check_fixture", fake_check)
    result = runner.run()
    assert not result.determinism_passed
    assert not result.passed
    assert result.exit_code == 1
    assert any("determinism" in reason for reason in result.failures())
