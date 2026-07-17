"""End-to-end benchmark runner tests over the committed corpus (Issue #94)."""

from __future__ import annotations

import io
import json
from pathlib import Path

from benchmark import report as report_module
from benchmark import run as run_module
from benchmark import runner


def test_full_benchmark_passes_and_reports_all_real_signals():
    result = runner.run()
    assert result.load_error is None
    assert result.passed
    assert result.exit_code == 0
    # Real, enforced-now signals.
    assert result.provenance.validity == 1
    assert result.provenance.total > 0
    assert result.determinism and all(r.deterministic for r in result.determinism)
    assert result.parity.passed
    assert result.diagnostics.passed
    assert result.scoring.available
    assert result.scoring.report is not None
    assert result.scoring.report.overall.precision == 1
    assert result.scoring.report.overall.recall == 1
    assert result.scoring.actual_provenance is not None
    assert result.scoring.actual_provenance.validity == 1
    # All three fixture classes and both languages are represented.
    assert set(result.corpus.by_class) == {"minimal", "realistic", "adversarial"}
    assert {"python", "typescript"} <= set(result.corpus.by_language)


def test_precision_recall_is_measured_by_the_real_extractors():
    result = runner.run()
    assert result.scoring.available
    assert result.scoring.report is not None
    assert result.scoring.report.overall.true_positives > 0
    assert result.scoring.report.false_positives == []
    assert result.scoring.report.false_negatives == []
    assert result.scoring_gate_passed


def test_reports_are_deterministic_and_serialisable():
    first = report_module.to_json(runner.run())
    second = report_module.to_json(runner.run())
    assert first == second, "JSON report must be byte-stable across runs"
    payload = json.loads(first)
    assert payload["result"] == "pass"
    assert payload["goldenFixtureProvenance"]["validity"] == "1.0000"
    assert payload["scoring"]["status"] == "scored"
    assert payload["scoring"]["realExtractorProvenance"]["validity"] == "1.0000"
    assert "deferred" not in first.lower()
    assert "unavailable" not in first.lower()
    markdown = report_module.to_markdown(runner.run())
    assert "Repository Intelligence Golden Benchmark" in markdown
    assert "lang:python" in markdown
    assert "class:adversarial" in markdown
    assert "False positives" in markdown
    assert "False negatives" in markdown
    assert "deferred" not in markdown.lower()
    assert "unavailable" not in markdown.lower()


def test_write_reports_emits_both_files(tmp_path: Path):
    json_path, markdown_path = report_module.write_reports(runner.run(), tmp_path / "out")
    assert json_path.is_file() and markdown_path.is_file()
    assert json.loads(json_path.read_text())["dataVersion"] == "ri-benchmark.v1"


def test_documented_command_writes_to_a_strict_cp1252_stream(tmp_path: Path, monkeypatch):
    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="cp1252", errors="strict")
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(run_module.sys, "stdout", stream)

    exit_code = run_module.main(["--report-dir", str(report_dir)])
    stream.flush()

    assert exit_code == 0
    assert b"RI Golden Benchmark: PASS" in output.getvalue()
    assert json.loads((report_dir / "benchmark.json").read_text(encoding="utf-8"))["result"] == "pass"
    assert "✅" in (report_dir / "benchmark.md").read_text(encoding="utf-8")
