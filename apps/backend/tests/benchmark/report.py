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
from benchmark.scorer import Counts, LabeledFact


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


def _citation_dict(report) -> dict[str, object]:
    return {
        "total": report.total,
        "valid": report.valid_count,
        "validity": _ratio(report.validity),
        "invalid": [
            {
                "fixtureId": check.fixture_id,
                "subject": check.subject,
                "path": check.path,
                "startLine": check.start_line,
                "endLine": check.end_line,
                "reason": check.reason,
            }
            for check in report.invalid
        ],
    }


def _fact_dict(item: LabeledFact) -> dict[str, object]:
    return {
        "fixtureId": item.fixture_id,
        "fixtureClass": item.fixture_class,
        "language": item.language,
        "factType": item.fact.fact_type,
        "kind": item.fact.kind,
        "subject": item.fact.subject,
        "key": repr(item.fact.key()),
    }


def to_json_dict(report: BenchmarkReport) -> dict[str, object]:
    scoring: dict[str, object]
    if not report.scoring.available or report.scoring.report is None:
        scoring = {
            "status": "unavailable",
            "reason": "The real extraction adapter did not produce measurements.",
        }
    else:
        score_report = report.scoring.report
        scoring = {
            "status": "scored",
            "overall": _counts_dict(score_report.overall),
            "byLanguage": {k: _counts_dict(v) for k, v in sorted(score_report.by_language.items())},
            "byClass": {k: _counts_dict(v) for k, v in sorted(score_report.by_class.items())},
            "falsePositives": [_fact_dict(item) for item in score_report.false_positives],
            "falseNegatives": [_fact_dict(item) for item in score_report.false_negatives],
            "realExtractorProvenance": (
                _citation_dict(report.scoring.actual_provenance)
                if report.scoring.actual_provenance is not None
                else None
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
        "goldenFixtureProvenance": _citation_dict(report.provenance),
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
        "goldenRegression": {
            "passed": report.golden_regression_passed,
            "unexpectedFactCount": len(report.scoring.report.false_positives) if report.scoring.report else None,
            "missingFactCount": len(report.scoring.report.false_negatives) if report.scoring.report else None,
        },
        "scoring": scoring,
        "failures": report.failures(),
    }


def to_json(report: BenchmarkReport) -> str:
    return json.dumps(to_json_dict(report), indent=2, sort_keys=True) + "\n"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _fact_label(item: LabeledFact) -> str:
    fact = item.fact
    identity = fact.subject or fact.referent or fact.object or fact.name or "(no subject)"
    return f"`{item.fixture_id}` · `{fact.fact_type}:{fact.kind}` · `{identity}`"


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
                ["precision", _ratio(report.thresholds.precision), "yes"],
                ["recall", _ratio(report.thresholds.recall), "yes"],
                ["provenance validity", _ratio(report.thresholds.provenance_validity), "yes"],
                ["determinism", _ratio(report.thresholds.determinism), "yes"],
            ],
        ),
        "",
        "## Golden fixture citation validity",
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

    lines += ["", "## Real-extraction determinism", ""]
    if report.determinism:
        lines.extend(
            _table(
                ["Fixture", "Deterministic", "Sealed hash A", "Sealed hash B"],
                [
                    [
                        r.fixture_id,
                        "yes" if r.deterministic else "**NO**",
                        f"`{r.sealed_hash_a}`",
                        f"`{r.sealed_hash_b}`",
                    ]
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

    lines += ["", "## Exact golden regression gate", ""]
    if report.scoring.report is None:
        lines.append("**Unavailable:** no real extraction comparison was produced.")
    else:
        lines.append(
            f"Exact committed-golden comparison: **{'pass' if report.golden_regression_passed else 'fail'}** "
            f"({len(report.scoring.report.false_positives)} unexpected, "
            f"{len(report.scoring.report.false_negatives)} missing facts)."
        )

    lines += ["", "## Extraction quality (precision / recall)", ""]
    if not report.scoring.available or report.scoring.report is None:
        lines.append("**Unavailable:** the real extraction adapter did not produce measurements.")
    else:
        score_report = report.scoring.report
        overall = score_report.overall
        lines.extend(
            _table(
                ["Scope", "TP", "FP", "FN", "Precision", "Recall"],
                [
                    [
                        "overall",
                        str(overall.true_positives),
                        str(overall.false_positives),
                        str(overall.false_negatives),
                        _ratio(overall.precision),
                        _ratio(overall.recall),
                    ]
                ]
                + [
                    [
                        f"lang:{lang}",
                        str(c.true_positives),
                        str(c.false_positives),
                        str(c.false_negatives),
                        _ratio(c.precision),
                        _ratio(c.recall),
                    ]
                    for lang, c in sorted(score_report.by_language.items())
                ]
                + [
                    [
                        f"class:{fixture_class}",
                        str(c.true_positives),
                        str(c.false_positives),
                        str(c.false_negatives),
                        _ratio(c.precision),
                        _ratio(c.recall),
                    ]
                    for fixture_class, c in sorted(score_report.by_class.items())
                ],
            )
        )
        actual_provenance = report.scoring.actual_provenance
        lines += ["", "## Real extractor citation validity", ""]
        if actual_provenance is None:
            lines.append("**Unavailable:** no real-extractor citation validation result was produced.")
        else:
            lines.append(
                f"{actual_provenance.valid_count} / {actual_provenance.total} citations valid "
                f"(validity **{_ratio(actual_provenance.validity)}**)."
            )
            if actual_provenance.invalid:
                lines.extend(
                    [
                        "",
                        *_table(
                            ["Fixture", "Subject", "Path", "Span", "Reason"],
                            [
                                [c.fixture_id, c.subject, c.path, f"{c.start_line}..{c.end_line}", c.reason]
                                for c in actual_provenance.invalid
                            ],
                        ),
                    ]
                )

        lines += ["", "## False positives", ""]
        if score_report.false_positives:
            lines.extend(f"- {_fact_label(item)}" for item in score_report.false_positives)
        else:
            lines.append("_None._")
        lines += ["", "## False negatives", ""]
        if score_report.false_negatives:
            lines.extend(f"- {_fact_label(item)}" for item in score_report.false_negatives)
        else:
            lines.append("_None._")

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
    if report.scoring.report is None:
        scoring = "unavailable"
    else:
        overall = report.scoring.report.overall
        scoring = f"precision {_ratio(overall.precision)}, recall {_ratio(overall.recall)}"
    actual_provenance = report.scoring.actual_provenance
    actual_citations = (
        f"{_ratio(actual_provenance.validity)} ({actual_provenance.valid_count}/{actual_provenance.total})"
        if actual_provenance is not None
        else "unavailable"
    )
    return (
        f"### RI Golden Benchmark: {status}\n\n"
        f"- Fixtures: {report.corpus.total}\n"
        f"- Golden fixture citation validity: {_ratio(report.provenance.validity)} "
        f"({report.provenance.valid_count}/{report.provenance.total})\n"
        f"- Real extractor citation validity: {actual_citations}\n"
        f"- Real-extraction determinism: "
        f"{sum(1 for r in report.determinism if r.deterministic)}/{len(report.determinism)} stable\n"
        f"- Support-matrix parity: {'pass' if report.parity.passed else 'fail'}\n"
        f"- Precision/recall: {scoring}\n"
    )


def to_console_summary(report: BenchmarkReport) -> str:
    """Render the step summary with ASCII-only status markers for local consoles."""

    status = "PASS" if report.passed else "FAIL"
    if report.scoring.report is None:
        scoring = "unavailable"
    else:
        overall = report.scoring.report.overall
        scoring = f"precision {_ratio(overall.precision)}, recall {_ratio(overall.recall)}"
    actual_provenance = report.scoring.actual_provenance
    actual_citations = (
        f"{_ratio(actual_provenance.validity)} ({actual_provenance.valid_count}/{actual_provenance.total})"
        if actual_provenance is not None
        else "unavailable"
    )
    return (
        f"RI Golden Benchmark: {status}\n"
        f"- Fixtures: {report.corpus.total}\n"
        f"- Golden fixture citation validity: {_ratio(report.provenance.validity)} "
        f"({report.provenance.valid_count}/{report.provenance.total})\n"
        f"- Real extractor citation validity: {actual_citations}\n"
        f"- Real-extraction determinism: "
        f"{sum(1 for r in report.determinism if r.deterministic)}/{len(report.determinism)} stable\n"
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
