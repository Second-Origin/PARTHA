"""Benchmark orchestration, gating, and exit-code policy (Issue #94 §F).

:func:`run` executes every stage over the committed corpus and returns a
:class:`BenchmarkReport` whose :meth:`~BenchmarkReport.exit_code` is non-zero
when any enforceable gate fails:

- a manifest is invalid;
- provenance validity is below threshold;
- determinism fails;
- the fixture/support-matrix parity check fails;
- an expected (required) diagnostic is missing for a declared blind spot;
- the real extraction adapter is unavailable;
- precision or recall is below threshold; or
- any citation emitted by the real extractors is invalid.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from benchmark import paths
from benchmark.adapter import ExtractionAdapter, default_adapter
from benchmark.determinism import DeterminismResult, check_fixture
from benchmark.loader import (
    LoadedFixture,
    ManifestError,
    SupportMatrix,
    Thresholds,
    load_corpus,
    load_support_matrix,
    load_thresholds,
)
from benchmark.provenance import ProvenanceResult, validate_expected, validate_fixture
from benchmark.scorer import LabeledFact, ScoreReport, score

BENCHMARK_DATA_VERSION = "ri-benchmark.v1"


@dataclass
class CorpusSummary:
    total: int
    by_class: dict[str, int]
    by_language: dict[str, int]


@dataclass
class ParityResult:
    supported_constructs: list[str]
    covered_constructs: list[str]
    uncovered_supported: list[str]
    uncovered_unsupported: list[str]

    @property
    def passed(self) -> bool:
        return not self.uncovered_supported and not self.uncovered_unsupported


@dataclass
class DiagnosticsCheck:
    missing: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.missing


@dataclass
class ScoringOutcome:
    available: bool
    report: ScoreReport | None = None
    actual_provenance: ProvenanceResult | None = None

@dataclass
class BenchmarkReport:
    data_version: str
    thresholds: Thresholds
    support_matrix_note: str
    corpus: CorpusSummary
    fixtures: list[LoadedFixture]
    provenance: ProvenanceResult
    determinism: list[DeterminismResult]
    parity: ParityResult
    diagnostics: DiagnosticsCheck
    scoring: ScoringOutcome
    load_error: str | None = None

    @property
    def provenance_passed(self) -> bool:
        return self.provenance.validity >= self.thresholds.provenance_validity

    @property
    def determinism_passed(self) -> bool:
        return all(result.deterministic for result in self.determinism)

    @property
    def scoring_gate_passed(self) -> bool:
        """Require real measurements and enforce every extraction-quality gate."""

        if not self.scoring.available or self.scoring.report is None:
            return False
        overall = self.scoring.report.overall
        provenance_ok = (
            self.scoring.actual_provenance is not None
            and self.scoring.actual_provenance.validity >= self.thresholds.provenance_validity
        )
        return (
            overall.precision >= self.thresholds.precision
            and overall.recall >= self.thresholds.recall
            and provenance_ok
        )

    @property
    def passed(self) -> bool:
        if self.load_error is not None:
            return False
        return (
            self.provenance_passed
            and self.determinism_passed
            and self.parity.passed
            and self.diagnostics.passed
            and self.scoring_gate_passed
        )

    @property
    def exit_code(self) -> int:
        return 0 if self.passed else 1

    def failures(self) -> list[str]:
        reasons: list[str] = []
        if self.load_error is not None:
            reasons.append(f"corpus failed to load: {self.load_error}")
            return reasons
        if not self.provenance_passed:
            for check in self.provenance.invalid:
                reasons.append(f"provenance: {check.fixture_id} {check.subject} {check.path} — {check.reason}")
        if not self.determinism_passed:
            for result in self.determinism:
                if not result.deterministic:
                    reasons.append(
                        f"determinism: {result.fixture_id} sealed {result.sealed_hash_a} != {result.sealed_hash_b}"
                    )
        for construct in self.parity.uncovered_supported:
            reasons.append(f"parity: supported construct {construct!r} is not covered by any fixture")
        for construct in self.parity.uncovered_unsupported:
            reasons.append(f"parity: unsupported construct {construct!r} is not exercised by any fixture")
        reasons.extend(f"diagnostics: {item}" for item in self.diagnostics.missing)
        if not self.scoring.available or self.scoring.report is None:
            reasons.append("scoring: the real extraction adapter did not produce measurements")
        elif not self.scoring_gate_passed:
            overall = self.scoring.report.overall
            if overall.precision < self.thresholds.precision:
                reasons.append(
                    f"scoring: precision {float(overall.precision):.4f} is below "
                    f"{float(self.thresholds.precision):.4f}"
                )
            if overall.recall < self.thresholds.recall:
                reasons.append(
                    f"scoring: recall {float(overall.recall):.4f} is below "
                    f"{float(self.thresholds.recall):.4f}"
                )
            if self.scoring.actual_provenance is None:
                reasons.append("real extractor provenance: no citation validation result was produced")
            else:
                for check in self.scoring.actual_provenance.invalid:
                    reasons.append(
                        f"real extractor provenance: {check.fixture_id} {check.subject} "
                        f"{check.path} — {check.reason}"
                    )
        return reasons


def _corpus_summary(fixtures: list[LoadedFixture]) -> CorpusSummary:
    by_class: dict[str, int] = {}
    by_language: dict[str, int] = {}
    for fixture in fixtures:
        by_class[fixture.fixture_class] = by_class.get(fixture.fixture_class, 0) + 1
        by_language[fixture.language] = by_language.get(fixture.language, 0) + 1
    return CorpusSummary(total=len(fixtures), by_class=dict(sorted(by_class.items())), by_language=dict(sorted(by_language.items())))


def _covered_constructs(fixtures: list[LoadedFixture]) -> set[str]:
    covered: set[str] = set()
    for fixture in fixtures:
        covered.update(fixture.constructs_covered)
        for expected in fixture.expected:
            covered.update(expected.constructs)
    return covered


def _parity(fixtures: list[LoadedFixture], support_matrix: SupportMatrix) -> ParityResult:
    covered = _covered_constructs(fixtures)
    supported = set(support_matrix.supported_ids())
    unsupported = {cid for cid, spec in support_matrix.constructs.items() if not spec.supported}
    return ParityResult(
        supported_constructs=sorted(supported),
        covered_constructs=sorted(covered),
        uncovered_supported=sorted(supported - covered),
        uncovered_unsupported=sorted(unsupported - covered),
    )


def _diagnostics_check(fixtures: list[LoadedFixture], support_matrix: SupportMatrix) -> DiagnosticsCheck:
    """Every unsupported construct with a required diagnostic must have a fixture
    that declares that construct and emits a diagnostic with the required code."""

    declared: set[tuple[str, str]] = set()
    for fixture in fixtures:
        for expected in fixture.expected:
            if expected.group == "diagnostics":
                for construct in expected.constructs:
                    declared.add((construct, expected.fact.kind))
    missing: list[str] = []
    for cid, spec in sorted(support_matrix.constructs.items()):
        if spec.supported or spec.expected_diagnostic is None:
            continue
        if (cid, spec.expected_diagnostic) not in declared:
            missing.append(f"unsupported construct {cid!r} requires a {spec.expected_diagnostic} diagnostic in some fixture")
    return DiagnosticsCheck(missing=missing)


def _labeled(fixture: LoadedFixture, fact: Fact, constructs: tuple[str, ...] = ()) -> LabeledFact:
    return LabeledFact(
        fact=fact,
        language=fixture.language,
        fixture_class=fixture.fixture_class,
        fixture_id=fixture.fixture_id,
        constructs=constructs,
    )


def _run_scoring(fixtures: list[LoadedFixture], adapter: ExtractionAdapter) -> ScoringOutcome:
    if not adapter.available:
        return ScoringOutcome(available=False)
    expected: list[LabeledFact] = []
    actual: list[LabeledFact] = []
    provenance = ProvenanceResult()
    scored_fact_types = getattr(adapter, "scored_fact_types", None)
    for fixture in fixtures:
        for record in fixture.expected:
            if scored_fact_types is not None and record.fact.fact_type not in scored_fact_types:
                continue
            expected.append(_labeled(fixture, record.fact, record.constructs))
        emitted = adapter.extract(fixture)
        for fact in emitted:
            actual.append(_labeled(fixture, fact))
        provenance.checks.extend(validate_fixture(fixture, emitted).checks)
    return ScoringOutcome(available=True, report=score(expected, actual), actual_provenance=provenance)


def run(
    *,
    fixtures_dir: Path = paths.FIXTURES_DIR,
    support_matrix_path: Path = paths.SUPPORT_MATRIX_PATH,
    thresholds_path: Path = paths.THRESHOLDS_PATH,
    adapter: ExtractionAdapter | None = None,
    determinism_tmp: Path | None = None,
) -> BenchmarkReport:
    """Run the full benchmark and return a gated :class:`BenchmarkReport`."""

    adapter = adapter or default_adapter()
    thresholds = load_thresholds(thresholds_path)

    try:
        support_matrix = load_support_matrix(support_matrix_path)
        fixtures = load_corpus(fixtures_dir, support_matrix)
    except ManifestError as exc:
        return BenchmarkReport(
            data_version=BENCHMARK_DATA_VERSION,
            thresholds=thresholds,
            support_matrix_note="Support-matrix or corpus validation failed.",
            corpus=CorpusSummary(0, {}, {}),
            fixtures=[],
            provenance=ProvenanceResult(),
            determinism=[],
            parity=ParityResult([], [], [], []),
            diagnostics=DiagnosticsCheck(),
            scoring=ScoringOutcome(available=False),
            load_error=str(exc),
        )

    provenance = ProvenanceResult()
    for fixture in fixtures:
        provenance.checks.extend(validate_expected(fixture).checks)

    determinism: list[DeterminismResult] = []
    deterministic_fixtures = [fixture for fixture in fixtures if fixture.deterministic]
    if deterministic_fixtures:
        tmp_context = None
        base = determinism_tmp
        if base is None:
            tmp_context = tempfile.TemporaryDirectory(prefix="ri-benchmark-det-")
            base = Path(tmp_context.name)
        try:
            for index, fixture in enumerate(deterministic_fixtures):
                determinism.append(check_fixture(fixture, base / f"det-{index}.db"))
        finally:
            if tmp_context is not None:
                tmp_context.cleanup()

    return BenchmarkReport(
        data_version=BENCHMARK_DATA_VERSION,
        thresholds=thresholds,
        support_matrix_note=support_matrix.note,
        corpus=_corpus_summary(fixtures),
        fixtures=fixtures,
        provenance=provenance,
        determinism=determinism,
        parity=_parity(fixtures, support_matrix),
        diagnostics=_diagnostics_check(fixtures, support_matrix),
        scoring=_run_scoring(fixtures, adapter),
    )
