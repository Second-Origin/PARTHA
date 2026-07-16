"""Citation / provenance validation against the stored fixture revision.

For every fact that carries evidence, this independently re-derives the RFC-0001
§6.2 checks from the *stored bytes* — it does not trust the loader or the fact
model. That makes it (a) a real gate on the golden corpus now and (b) the exact
validator that runs over a live extractor's citations once #89/#90 merge.

A citation is valid iff:

- its path normalizes to a repository-relative POSIX path that cannot escape the
  revision root (RFC §4.2);
- the file exists in the fixture's stored revision and is strict-UTF-8 text
  (not binary, not malformed);
- ``1 <= start_line <= end_line <= logical_line_count`` where
  ``logical_line_count = 1 + count(U+000A)`` (RFC §6.2);
- file-granularity evidence spans exactly ``1..logical_line_count``;
- the extractor name and version are non-empty and declared in the snapshot's
  producer set.

Provenance validity is ``valid_citations / total_citations`` and the benchmark
gate requires it to be exactly ``1``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from app.intelligence import canonical

from benchmark.facts import EvidenceSpan, Fact
from benchmark.loader import LoadedFixture
from benchmark.sourcefiles import SourceDecodeError, decode_strict_utf8, is_binary, logical_line_count


@dataclass(frozen=True)
class CitationCheck:
    fixture_id: str
    subject: str
    path: str
    start_line: int
    end_line: int
    granularity: str
    valid: bool
    reason: str = ""


@dataclass
class ProvenanceResult:
    checks: list[CitationCheck] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def invalid(self) -> list[CitationCheck]:
        return [check for check in self.checks if not check.valid]

    @property
    def valid_count(self) -> int:
        return self.total - len(self.invalid)

    @property
    def validity(self) -> Fraction:
        # No citations is vacuously valid (nothing wrong was emitted).
        return Fraction(1) if self.total == 0 else Fraction(self.valid_count, self.total)


def _check_span(
    fixture: LoadedFixture,
    subject: str,
    span: EvidenceSpan,
    producer_set: set[str],
) -> CitationCheck:
    def result(valid: bool, reason: str = "") -> CitationCheck:
        return CitationCheck(
            fixture.fixture_id, subject, span.path, span.start_line, span.end_line, span.granularity, valid, reason
        )

    if not span.extractor or not span.extractor_version:
        return result(False, "extractor name/version must be non-empty")
    if f"{span.extractor}@{span.extractor_version}" not in producer_set:
        return result(False, f"undeclared producer {span.extractor}@{span.extractor_version}")
    try:
        normalized = canonical.normalize_repo_path(span.path)
    except canonical.PathEscapeError as exc:
        return result(False, f"path escapes revision root: {exc}")
    if normalized != span.path or not normalized:
        return result(False, "path is not in normalized repository-relative form")

    source = fixture.directory / normalized
    if not source.is_file():
        return result(False, "cited file does not exist in the stored revision")
    data = source.read_bytes()
    if is_binary(data):
        return result(False, "cited file is binary (no line spans permitted)")
    try:
        text = decode_strict_utf8(data)
    except SourceDecodeError:
        return result(False, "cited file is not strict UTF-8")
    line_count = logical_line_count(text)
    if not (1 <= span.start_line <= span.end_line <= line_count):
        return result(False, f"span {span.start_line}..{span.end_line} outside 1..{line_count}")
    if span.granularity == "file" and not (span.start_line == 1 and span.end_line == line_count):
        return result(False, f"file-granularity span must be 1..{line_count}")
    return result(True)


def validate_fixture(fixture: LoadedFixture, facts: list[Fact]) -> ProvenanceResult:
    """Validate every citation carried by ``facts`` against ``fixture``'s revision."""

    producer_set = set(fixture.producer_version_set)
    result = ProvenanceResult()
    for fact in facts:
        for span in fact.evidence:
            result.checks.append(_check_span(fixture, fact.subject or fact.kind, span, producer_set))
    return result


def validate_expected(fixture: LoadedFixture) -> ProvenanceResult:
    """Convenience: validate the fixture's own golden citations."""

    return validate_fixture(fixture, [expected.fact for expected in fixture.expected])
