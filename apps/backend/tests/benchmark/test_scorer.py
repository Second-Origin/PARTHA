"""Scorer unit tests with intentionally controlled TP/FP/FN inputs (Issue #94).

These never touch a fixture or an extractor: they feed hand-built expected and
actual fact sets straight into the scorer so its arithmetic is proven in
isolation — including duplicates, wrong spans, wrong kinds, empty expected sets,
missing diagnostics, and both zero-denominator cases.
"""

from __future__ import annotations

from fractions import Fraction

from benchmark.facts import EvidenceSpan, Fact
from benchmark.scorer import LabeledFact, score


def _span(path: str, start: int, end: int, granularity: str = "span") -> EvidenceSpan:
    return EvidenceSpan(path, start, end, "python-ast", "1.0.0", granularity)


def _node(stable_key: str, start: int, end: int, *, kind: str = "symbol") -> Fact:
    return Fact(
        fact_type="node",
        kind=kind,
        subject=stable_key,
        truth_class="observed",
        evidence=(_span(stable_key.split("::")[0].removeprefix("file:"), start, end),),
    )


def _diagnostic(code: str, subject: str) -> Fact:
    return Fact(fact_type="diagnostic", kind=code, subject=subject, severity="info", producer="python-ast@1.0.0")


def _labeled(fact: Fact, *, language: str = "python", fixture_class: str = "minimal", fixture_id: str = "fx") -> LabeledFact:
    return LabeledFact(fact=fact, language=language, fixture_class=fixture_class, fixture_id=fixture_id)


def test_perfect_match_scores_one_precision_and_recall():
    facts = [_labeled(_node("file:a.py::f", 1, 3)), _labeled(_node("file:a.py::g", 5, 9))]
    report = score(facts, list(facts))
    assert report.overall.true_positives == 2
    assert report.overall.false_positives == 0
    assert report.overall.false_negatives == 0
    assert report.overall.precision == Fraction(1)
    assert report.overall.recall == Fraction(1)


def test_extra_actual_fact_is_a_false_positive():
    expected = [_labeled(_node("file:a.py::f", 1, 3))]
    actual = [_labeled(_node("file:a.py::f", 1, 3)), _labeled(_node("file:a.py::ghost", 10, 12))]
    report = score(expected, actual)
    assert report.overall.true_positives == 1
    assert report.overall.false_positives == 1
    assert report.overall.false_negatives == 0
    assert report.overall.precision == Fraction(1, 2)
    assert report.overall.recall == Fraction(1)


def test_missing_expected_fact_is_a_false_negative():
    expected = [_labeled(_node("file:a.py::f", 1, 3)), _labeled(_node("file:a.py::g", 5, 9))]
    actual = [_labeled(_node("file:a.py::f", 1, 3))]
    report = score(expected, actual)
    assert report.overall.true_positives == 1
    assert report.overall.false_negatives == 1
    assert report.overall.false_positives == 0
    assert report.overall.recall == Fraction(1, 2)
    assert report.overall.precision == Fraction(1)


def test_right_name_wrong_span_is_both_a_miss_and_an_invention():
    expected = [_labeled(_node("file:a.py::f", 1, 3))]
    actual = [_labeled(_node("file:a.py::f", 2, 4))]  # same symbol, wrong span
    report = score(expected, actual)
    assert report.overall.true_positives == 0
    assert report.overall.false_negatives == 1
    assert report.overall.false_positives == 1
    assert report.overall.precision == Fraction(0)
    assert report.overall.recall == Fraction(0)


def test_wrong_fact_kind_does_not_match():
    expected = [_labeled(_node("file:a.py::C", 1, 8, kind="symbol"))]
    actual = [_labeled(_node("file:a.py::C", 1, 8, kind="module"))]
    report = score(expected, actual)
    assert report.overall.true_positives == 0
    assert report.overall.false_positives == 1
    assert report.overall.false_negatives == 1


def test_duplicate_actual_fact_counts_one_tp_and_one_fp():
    expected = [_labeled(_node("file:a.py::f", 1, 3))]
    actual = [_labeled(_node("file:a.py::f", 1, 3)), _labeled(_node("file:a.py::f", 1, 3))]
    report = score(expected, actual)
    assert report.overall.true_positives == 1
    assert report.overall.false_positives == 1
    assert report.overall.false_negatives == 0
    assert report.overall.precision == Fraction(1, 2)


def test_empty_expected_with_invented_facts_is_zero_precision_not_perfect():
    expected: list[LabeledFact] = []
    actual = [_labeled(_node("file:a.py::ghost", 1, 2))]
    report = score(expected, actual)
    assert report.overall.true_positives == 0
    assert report.overall.false_positives == 1
    assert report.overall.precision == Fraction(0)  # NOT a manufactured 1.0
    assert report.overall.recall == Fraction(1)      # nothing was expected


def test_empty_expected_and_empty_actual_is_defined_as_perfect():
    report = score([], [])
    assert report.overall.precision == Fraction(1)
    assert report.overall.recall == Fraction(1)


def test_missing_required_diagnostic_is_a_false_negative():
    expected = [_labeled(_diagnostic("RI-EXT-UNSUPPORTED", "file:a.py::dynamic"))]
    actual: list[LabeledFact] = []  # extractor stayed silent instead of diagnosing
    report = score(expected, actual)
    assert report.overall.false_negatives == 1
    assert report.overall.recall == Fraction(0)


def test_per_language_and_per_class_breakdowns_are_attributed_correctly():
    expected = [
        _labeled(_node("file:a.py::f", 1, 3), language="python", fixture_class="minimal"),
        _labeled(_node("file:a.ts::g", 1, 3), language="typescript", fixture_class="realistic"),
    ]
    actual = [
        _labeled(_node("file:a.py::f", 1, 3), language="python", fixture_class="minimal"),
        _labeled(_node("file:a.ts::ghost", 9, 9), language="typescript", fixture_class="realistic"),
    ]
    report = score(expected, actual)
    assert report.by_language["python"].true_positives == 1
    assert report.by_language["python"].false_positives == 0
    assert report.by_language["typescript"].true_positives == 0
    assert report.by_language["typescript"].false_negatives == 1
    assert report.by_language["typescript"].false_positives == 1
    assert report.by_class["realistic"].recall == Fraction(0)
    assert report.by_class["minimal"].precision == Fraction(1)
