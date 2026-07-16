"""Deterministic, human- and machine-readable benchmark reports (Issue #94 §F).

Renders a :class:`~benchmark.runner.BenchmarkReport` to Markdown and JSON with
sorted, stable content and no absolute paths, secrets, or repository source, so
the output is safe to publish in CI logs and diff across runs.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from benchmark.runner import BenchmarkReport
from benchmark.scorer import Counts


def _ratio(value: Fraction) -> str:
    return f"{float(value):.4f}"


def _counts_dict(counts: Counts) -> dict[str, object]:
    return {
        "truePositives": counts.true_positives,
        "falsePositives": counts.false_positives,
        "falseNegatives": counts.false_negatives,
        "precision": _ratio(counts.precision),
        "recall": _ratio(counts.recall),
    }


def to_json_dict(report: BenchmarkReport) -> dict[str, object]:
    scoring: dict[str, object]
    if report.scoring.deferred:
        scoring = {
            "status": "deferred",
            "reason": "No extractor available; precision/recall scoring lands with #89/#90.",
        }
    else:
        assert report.scoring.report is not None
        scoring = {
            "status": "scored",
            "overall": _counts_dict(report.scoring.report.overall),
            "byLanguage": {k: _counts_dict(v) for k, v in sorted(report.scoring.report.by_language.items())},
            "byClass": {k: _counts_dict(v) for k, v in sorted(report.scoring.report.by_class.items())},
            "actualProvenanceValidity": (
                _ratio(report.scoring.actual_provenance.validity) if report.scoring.actual_provenance else None
            ),
        }
    return {
        "dataVersion": report.data_version,
        "result": "pass" if report.passed else "fail",
        "thresholds": {
            "precision": _ratio(report.thresholds.precision),
            "recall": _ratio(report.thresholds.recall),
            "provenanceValidity": _ratio(report.thresholds.provenance_validity),
            "determinism": _ratio(report.thresholds.determinism),
        },
        "supportMatrixNote": report.support_matrix_note,
        "corpus": {
            "total": report.corpus.total,
            "byClass": report.corpus.by_class,
            "byLanguage": report.corpus.by_language,
        },
        "fixtures": [
            {
                "fixtureId": fixture.fixture_id,
                "fixtureClass": fixture.fixture_class,
                "language": fixture.language,
                "revisionValue": fixture.revision_value(),
                "producerVersionSet": list(fixture.producer_version_set),
                "constructsCovered": list(fixture.constructs_covered),
                "expectedFactCount": len(fixture.expected),
                "deterministic": fixture.deterministic,
            }
            for fixture in report.fixtures
        ],
        "provenance": {
            "total": report.provenance.total,
            "valid": report.provenance.valid_count,
            "validity": _ratio(report.provenance.validity),
            "invalid": [
                {"fixtureId": c.fixture_id, "subject": c.subject, "path": c.path,
                 "startLine": c.start_line, "endLine": c.end_line, "reason": c.reason}
                for c in report.provenance.invalid
            ],
        },
        "determinism": [
            {
                "fixtureId": r.fixture_id,
                "deterministic": r.deterministic,
                "sealedHashA": r.sealed_hash_a,
                "sealedHashB": r.sealed_hash_b,
                "pureHashA": r.pure_hash_a,
                "pureHashB": r.pure_hash_b,
            }
            for r in report.determinism
        ],
        "supportMatrixParity": {
            "passed": report.parity.passed,
            "supportedConstructs": report.parity.supported_constructs,
            "coveredConstructs": report.parity.covered_constructs,
            "uncoveredSupported": report.parity.uncovered_supported,
            "uncoveredUnsupported": report.parity.uncovered_unsupported,
        },
        "requiredDiagnostics": {"passed": report.diagnostics.passed, "missing": report.diagnostics.missing},
        "scoring": scoring,
        "failures": report.failures(),
    }


def to_json(report: BenchmarkReport) -> str:
    return json.dumps(to_json_dict(report), indent=2, sort_keys=True) + "\n"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def to_markdown(report: BenchmarkReport) -> str:
    result = "✅ PASS" if report.passed else "❌ FAIL"
    lines: list[str] = [
        "# Repository Intelligence Golden Benchmark",
        "",
        f"**Result:** {result}  ",
        f"**Benchmark data version:** `{report.data_version}`  ",
        f"**Corpus:** {report.corpus.total} fixtures "
        f"({', '.join(f'{k}: {v}' for k, v in report.corpus.by_class.items())})",
        "",
        "## Thresholds",
        "",
        *_table(
            ["Metric", "Threshold", "Enforced now?"],
            [
                ["precision", _ratio(report.thresholds.precision), "when extractor available (#89/#90)"],
                ["recall", _ratio(report.thresholds.recall), "when extractor available (#89/#90)"],
                ["provenance validity", _ratio(report.thresholds.provenance_validity), "yes"],
                ["determinism", _ratio(report.thresholds.determinism), "yes"],
            ],
        ),
        "",
        "## Provenance / citation validity",
        "",
        f"{report.provenance.valid_count} / {report.provenance.total} citations valid "
        f"(validity **{_ratio(report.provenance.validity)}**).",
    ]
    if report.provenance.invalid:
        lines.append("")
        lines.extend(
            _table(
                ["Fixture", "Subject", "Path", "Span", "Reason"],
                [
                    [c.fixture_id, c.subject, c.path, f"{c.start_line}..{c.end_line}", c.reason]
                    for c in report.provenance.invalid
                ],
            )
        )

    lines += ["", "## Snapshot determinism", ""]
    if report.determinism:
        lines.extend(
            _table(
                ["Fixture", "Deterministic", "Canonical graph hash"],
                [
                    [r.fixture_id, "yes" if r.deterministic else "**NO**", f"`{r.sealed_hash_a}`"]
                    for r in report.determinism
                ],
            )
        )
    else:
        lines.append("_No deterministic fixtures declared._")

    lines += ["", "## Support-matrix parity", ""]
    lines.append(f"Parity: {'✅' if report.parity.passed else '❌'}  ")
    lines.append(
        f"Covered {len(report.parity.covered_constructs)} constructs; "
        f"{len(report.parity.uncovered_supported)} supported uncovered; "
        f"{len(report.parity.uncovered_unsupported)} unsupported unexercised."
    )

    lines += ["", "## Extraction quality (precision / recall)", ""]
    if report.scoring.deferred:
        lines.append(
            "> **Deferred.** No Repository Intelligence extractor is merged yet. Precision/recall "
            "scoring plugs into the adapter boundary once **#89/#90** merge their extractors and "
            "support matrices; it is intentionally **not** scored against the golden facts themselves."
        )
    else:
        assert report.scoring.report is not None
        overall = report.scoring.report.overall
        lines.extend(
            _table(
                ["Scope", "TP", "FP", "FN", "Precision", "Recall"],
                [["overall", str(overall.true_positives), str(overall.false_positives),
                  str(overall.false_negatives), _ratio(overall.precision), _ratio(overall.recall)]]
                + [
                    [f"lang:{lang}", str(c.true_positives), str(c.false_positives), str(c.false_negatives),
                     _ratio(c.precision), _ratio(c.recall)]
                    for lang, c in sorted(report.scoring.report.by_language.items())
                ],
            )
        )

    failures = report.failures()
    lines += ["", "## Failures", ""]
    if failures:
        lines.extend(f"- {reason}" for reason in failures)
    else:
        lines.append("_None._")
    lines.append("")
    return "\n".join(lines)


def to_step_summary(report: BenchmarkReport) -> str:
    status = "PASS ✅" if report.passed else "FAIL ❌"
    scoring = "deferred (#89/#90)" if report.scoring.deferred else "scored"
    return (
        f"### RI Golden Benchmark: {status}\n\n"
        f"- Fixtures: {report.corpus.total}\n"
        f"- Provenance validity: {_ratio(report.provenance.validity)} "
        f"({report.provenance.valid_count}/{report.provenance.total})\n"
        f"- Determinism: {sum(1 for r in report.determinism if r.deterministic)}/{len(report.determinism)} stable\n"
        f"- Support-matrix parity: {'pass' if report.parity.passed else 'fail'}\n"
        f"- Precision/recall: {scoring}\n"
    )


def write_reports(report: BenchmarkReport, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "benchmark.json"
    markdown_path = directory / "benchmark.md"
    json_path.write_text(to_json(report), encoding="utf-8")
    markdown_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, markdown_path
