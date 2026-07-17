"""Precision / recall scoring over the benchmark fact model.

The scorer compares two collections of :class:`~benchmark.facts.Fact` — the
independently authored ``expected`` (golden) facts and the ``actual`` facts an
extractor emitted — by their exact semantic identity (:meth:`Fact.key`). It
reports true positives, false positives, false negatives, precision and recall,
aggregate and per-language / per-fixture-class (Issue #94 "Report both aggregate
and per-language / per-fixture-class metrics").

Design decisions that matter for correctness:

- **Multiset matching.** Counting is multiset-aware, so a fact emitted twice
  when it was expected once scores one true positive and one false positive
  (a duplicate is a real defect, not a free pass).
- **Fixture-scoped matching.** Identity maps use ``(fixture_id, Fact.key())`` so
  identical repository-relative paths in separate fixtures cannot cross-match.
- **Wrong span ⇒ miss.** Because the evidence span set is part of the identity,
  a right-named fact with a wrong line span is one false negative (the expected
  span is unmet) and one false positive (the wrong span was invented).
- **Zero denominators are explicit.** ``precision = 1`` when nothing was emitted
  (``tp + fp == 0``) and ``recall = 1`` when nothing was expected
  (``tp + fn == 0``). A fixture with *no* expected facts therefore cannot
  manufacture a perfect precision if the extractor invents facts: those are
  false positives, ``tp + fp > 0``, and precision drops.
- **Threshold comparisons are exact.** Gate checks use :class:`fractions.Fraction`
  cross-multiplication, never lossy float ``>=``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction

from benchmark.facts import Fact


@dataclass(frozen=True)
class LabeledFact:
    """A fact tagged with the fixture dimensions used for per-dimension metrics."""

    fact: Fact
    language: str
    fixture_class: str
    fixture_id: str
    constructs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Counts:
    """True/false positive/negative counts with derived precision and recall."""

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> Fraction:
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            return Fraction(1)
        return Fraction(self.true_positives, denominator)

    @property
    def recall(self) -> Fraction:
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            return Fraction(1)
        return Fraction(self.true_positives, denominator)


@dataclass
class ScoreReport:
    overall: Counts
    by_language: dict[str, Counts] = field(default_factory=dict)
    by_class: dict[str, Counts] = field(default_factory=dict)
    true_positives: list[LabeledFact] = field(default_factory=list)
    false_positives: list[LabeledFact] = field(default_factory=list)
    false_negatives: list[LabeledFact] = field(default_factory=list)


def _counts_by(dimension, positives_expected, positives_actual, negatives_expected) -> dict[str, Counts]:
    """Build per-dimension counts. TP/FN are attributed to the expected side,
    FP to the actual side, so a dimension label always comes from a real fact."""

    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    for labeled in positives_expected:
        tp[dimension(labeled)] += 1
    for labeled in positives_actual:
        fp[dimension(labeled)] += 1
    for labeled in negatives_expected:
        fn[dimension(labeled)] += 1
    keys = sorted(set(tp) | set(fp) | set(fn))
    return {key: Counts(tp[key], fp[key], fn[key]) for key in keys}


def score(expected: list[LabeledFact], actual: list[LabeledFact]) -> ScoreReport:
    """Score ``actual`` against ``expected`` and return a :class:`ScoreReport`."""

    expected_by_key: dict[tuple, list[LabeledFact]] = defaultdict(list)
    actual_by_key: dict[tuple, list[LabeledFact]] = defaultdict(list)
    for labeled in expected:
        expected_by_key[(labeled.fixture_id, labeled.fact.key())].append(labeled)
    for labeled in actual:
        actual_by_key[(labeled.fixture_id, labeled.fact.key())].append(labeled)

    true_positives: list[LabeledFact] = []
    false_negatives: list[LabeledFact] = []
    false_positives: list[LabeledFact] = []

    for key in sorted(set(expected_by_key) | set(actual_by_key), key=repr):
        exps = sorted(expected_by_key.get(key, []), key=lambda item: item.fixture_id)
        acts = sorted(actual_by_key.get(key, []), key=lambda item: item.fixture_id)
        matched = min(len(exps), len(acts))
        true_positives.extend(exps[:matched])   # attribute matches to the golden side
        false_negatives.extend(exps[matched:])  # expected facts never produced
        false_positives.extend(acts[matched:])  # surplus / invented actual facts

    overall = Counts(len(true_positives), len(false_positives), len(false_negatives))
    return ScoreReport(
        overall=overall,
        by_language=_counts_by(lambda item: item.language, true_positives, false_positives, false_negatives),
        by_class=_counts_by(lambda item: item.fixture_class, true_positives, false_positives, false_negatives),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )
