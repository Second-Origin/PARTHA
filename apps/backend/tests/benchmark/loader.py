"""Strict, deterministic loading and validation of the fixture corpus.

The loader is the benchmark's integrity gate. It refuses to load anything it
cannot fully validate against the merged #86 evidence contract, so a malformed
or dishonest fixture fails loudly instead of silently degrading a score. It
fails clearly on every condition Issue #94 enumerates:

unsupported schema versions; duplicate fixture ids; duplicate expected
identities; missing source files; absolute paths; ``..`` escapes; invalid line
ranges; undeclared support-matrix construct ids; malformed expected facts;
unsupported languages; inconsistent producer versions; facts missing mandatory
evidence; and accidental machine-blessed output committed as source truth.

Golden facts are *loaded and checked* here, never generated: there is no
"bless current output" path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.intelligence import canonical

from benchmark import schema
from benchmark.facts import EvidenceSpan, Fact, canonical_value
from benchmark.sourcefiles import (
    SourceDecodeError,
    decode_strict_utf8,
    is_binary,
    logical_line_count,
    read_bytes,
)


class ManifestError(ValueError):
    """A fixture, support matrix, or thresholds file failed strict validation."""


# ---------------------------------------------------------------------------
# Support matrix and thresholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstructSpec:
    construct_id: str
    language: str
    supported: bool
    description: str
    expected_diagnostic: str | None


@dataclass(frozen=True)
class SupportMatrix:
    constructs: dict[str, ConstructSpec]
    note: str = ""

    def __contains__(self, construct_id: str) -> bool:
        return construct_id in self.constructs

    def supported_ids(self) -> list[str]:
        return sorted(cid for cid, spec in self.constructs.items() if spec.supported)


@dataclass(frozen=True)
class Thresholds:
    precision: Fraction
    recall: Fraction
    provenance_validity: Fraction
    determinism: Fraction


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise ManifestError(f"missing required file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path}: invalid JSON: {exc}") from exc


def load_support_matrix(path: Path) -> SupportMatrix:
    data = _read_json(path)
    if data.get("schemaVersion") != schema.SUPPORT_MATRIX_SCHEMA_VERSION:
        raise ManifestError(
            f"{path}: unsupported support-matrix schema version {data.get('schemaVersion')!r}"
        )
    constructs: dict[str, ConstructSpec] = {}
    raw = data.get("constructs")
    if not isinstance(raw, dict) or not raw:
        raise ManifestError(f"{path}: 'constructs' must be a non-empty object")
    for construct_id, spec in sorted(raw.items()):
        language = spec.get("language")
        if language not in schema.LANGUAGES:
            raise ManifestError(f"{path}: construct {construct_id!r} has unsupported language {language!r}")
        supported = spec.get("supported")
        if not isinstance(supported, bool):
            raise ManifestError(f"{path}: construct {construct_id!r} 'supported' must be boolean")
        expected_diagnostic = spec.get("expectedDiagnostic")
        if not supported and expected_diagnostic not in schema.DIAGNOSTIC_CODES:
            raise ManifestError(
                f"{path}: unsupported construct {construct_id!r} must declare a valid 'expectedDiagnostic'"
            )
        if expected_diagnostic is not None and expected_diagnostic not in schema.DIAGNOSTIC_CODES:
            raise ManifestError(f"{path}: construct {construct_id!r} has unknown diagnostic {expected_diagnostic!r}")
        constructs[construct_id] = ConstructSpec(
            construct_id=construct_id,
            language=language,
            supported=supported,
            description=str(spec.get("description", "")),
            expected_diagnostic=expected_diagnostic,
        )
    return SupportMatrix(constructs=constructs, note=str(data.get("note", "")))


def _fraction(value: Any, *, where: str) -> Fraction:
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise ManifestError(f"{where}: invalid threshold value {value!r}") from exc


def load_thresholds(path: Path) -> Thresholds:
    data = _read_json(path)
    if data.get("schemaVersion") != schema.THRESHOLDS_SCHEMA_VERSION:
        raise ManifestError(f"{path}: unsupported thresholds schema version {data.get('schemaVersion')!r}")
    return Thresholds(
        precision=_fraction(data.get("precision"), where=f"{path} precision"),
        recall=_fraction(data.get("recall"), where=f"{path} recall"),
        provenance_validity=_fraction(data.get("provenanceValidity"), where=f"{path} provenanceValidity"),
        determinism=_fraction(data.get("determinism"), where=f"{path} determinism"),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpectedFact:
    """One loaded expected fact: the comparable :class:`Fact` plus provenance metadata."""

    group: str
    fact: Fact
    constructs: tuple[str, ...]
    raw: dict[str, Any]


@dataclass(frozen=True)
class LoadedFixture:
    fixture_id: str
    fixture_class: str
    language: str
    title: str
    description: str
    directory: Path
    source_root: str
    revision_identity: str
    producer_version_set: tuple[str, ...]
    constructs_covered: tuple[str, ...]
    deterministic: bool
    expected: tuple[ExpectedFact, ...]

    def source_files(self) -> dict[str, bytes]:
        """Every stored byte of the synthetic repository (everything but the manifest)."""

        files: dict[str, bytes] = {}
        for path in sorted(self.directory.rglob("*")):
            if not path.is_file() or path.name == "manifest.json":
                continue
            relative = path.relative_to(self.directory).as_posix()
            files[relative] = path.read_bytes()
        return files

    def revision_value(self) -> str:
        """A real, reproducible ``sha256:`` upload identity over the stored bytes.

        Content-addressed, not a fabricated Git SHA: the SHA-256 over the sorted
        ``{path: sha256(bytes)}`` map of the synthetic repository (RFC-0001 §3.2
        upload identity).
        """

        digest_map = {path: canonical.sha256_hex(data) for path, data in self.source_files().items()}
        return canonical.sha256_prefixed(canonical.canonical_json_bytes(digest_map))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def _evidence_span(raw: dict[str, Any], *, where: str, producers: set[str]) -> EvidenceSpan:
    for required in ("path", "startLine", "endLine", "extractor", "extractorVersion"):
        _require(required in raw, f"{where}: evidence missing required field {required!r}")
    extractor = str(raw["extractor"])
    version = str(raw["extractorVersion"])
    _require(
        f"{extractor}@{version}" in producers,
        f"{where}: evidence producer {extractor}@{version!r} is not in producerVersionSet",
    )
    try:
        path = canonical.normalize_repo_path(str(raw["path"]))
    except canonical.PathEscapeError as exc:
        raise ManifestError(f"{where}: evidence path {raw['path']!r} is absolute or escapes root ({exc})") from exc
    _require(bool(path), f"{where}: evidence path must be repository-relative and non-empty")
    start, end = raw["startLine"], raw["endLine"]
    _require(isinstance(start, int) and isinstance(end, int), f"{where}: line numbers must be integers")
    granularity = raw.get("granularity", "span")
    _require(granularity in ("span", "file"), f"{where}: granularity must be 'span' or 'file'")
    return EvidenceSpan(path, start, end, extractor, version, granularity)


def _build_fact(group: str, raw: dict[str, Any], *, where: str, producers: set[str]) -> Fact:
    if group == "nodes":
        node_kind = str(raw.get("nodeKind", ""))
        _require(bool(node_kind), f"{where}: node missing 'nodeKind'")
        try:
            stable_key = canonical.normalize_stable_key(node_kind, str(raw.get("stableKey", "")))
        except (canonical.CanonicalizationError, canonical.PathEscapeError) as exc:
            raise ManifestError(f"{where}: invalid node stableKey ({exc})") from exc
        evidence = tuple(_evidence_span(item, where=where, producers=producers) for item in raw.get("evidence", []))
        _require(len(evidence) >= 1, f"{where}: observed node {stable_key!r} must carry >=1 evidence record")
        return Fact(
            fact_type="node",
            kind=node_kind,
            subject=stable_key,
            name=str(raw.get("name", "")),
            language=str(raw.get("language", "")),
            truth_class="observed",
            evidence=evidence,
        )
    if group == "edges":
        predicate = canonical.validate_predicate(str(raw.get("predicate", "")))
        subject = canonical.normalize_stable_key(str(raw["subjectKind"]), str(raw["subjectKey"]))
        obj = canonical.normalize_stable_key(str(raw["objectKind"]), str(raw["objectKey"]))
        evidence = tuple(_evidence_span(item, where=where, producers=producers) for item in raw.get("evidence", []))
        _require(len(evidence) >= 1, f"{where}: edge must carry >=1 evidence record")
        producer = f"{raw.get('producer', '')}@{raw.get('producerVersion', '')}"
        _require(producer in producers, f"{where}: edge producer {producer!r} not in producerVersionSet")
        return Fact(
            fact_type="edge",
            kind=predicate,
            subject=subject,
            object=obj,
            predicate=predicate,
            truth_class="resolved",
            evidence=evidence,
        )
    if group == "observations":
        observed_kind = canonical.validate_predicate(str(raw.get("observedKind", "")))
        subject = canonical.normalize_stable_key(str(raw["subjectKind"]), str(raw["subjectKey"]))
        span = _evidence_span(raw["evidence"], where=where, producers=producers)
        return Fact(
            fact_type="observation",
            kind=observed_kind,
            subject=subject,
            predicate=observed_kind,
            referent=str(raw.get("referentText", "")),
            evidence=(span,),
        )
    if group == "assertions":
        predicate = canonical.validate_predicate(str(raw.get("predicate", "")))
        subject = canonical.normalize_stable_key(str(raw["subjectKind"]), str(raw["subjectKey"]))
        producer = f"{raw.get('producer', '')}@{raw.get('producerVersion', '')}"
        _require(producer in producers, f"{where}: assertion producer {producer!r} not in producerVersionSet")
        return Fact(
            fact_type="assertion",
            kind=predicate,
            subject=subject,
            predicate=predicate,
            truth_class="inferred",
            value=canonical_value(raw.get("value", {})),
        )
    if group == "diagnostics":
        code = str(raw.get("code", ""))
        _require(code in schema.DIAGNOSTIC_CODES, f"{where}: unknown diagnostic code {code!r}")
        severity = str(raw.get("severity", ""))
        _require(severity in schema.DIAGNOSTIC_SEVERITIES, f"{where}: invalid severity {severity!r}")
        producer = str(raw.get("producer", ""))
        _require(producer in producers, f"{where}: diagnostic producer {producer!r} not in producerVersionSet")
        path = raw.get("path")
        normalized_path = None
        if path is not None:
            try:
                normalized_path = canonical.normalize_repo_path(str(path))
            except canonical.PathEscapeError as exc:
                raise ManifestError(f"{where}: diagnostic path {path!r} escapes root ({exc})") from exc
        span = raw.get("span")
        if span is not None:
            _require(
                isinstance(span.get("startLine"), int) and isinstance(span.get("endLine"), int),
                f"{where}: diagnostic span lines must be integers",
            )
            _require(
                1 <= span["startLine"] <= span["endLine"],
                f"{where}: diagnostic span must be one-based and inclusive",
            )
        location = canonical_value(
            {"path": normalized_path, "span": {"startLine": span["startLine"], "endLine": span["endLine"]} if span else None}
        )
        return Fact(
            fact_type="diagnostic",
            kind=code,
            subject=str(raw.get("subject", "")),
            object=str(raw.get("object", "")),
            severity=severity,
            producer=producer,
            value=location,
        )
    raise ManifestError(f"{where}: unknown fact group {group!r}")


def _validate_evidence_against_source(
    fixture_dir: Path, span: EvidenceSpan, *, where: str
) -> None:
    """Enforce RFC-0001 §6.2: the cited file exists, decodes, and the span is in range."""

    source_path = fixture_dir / span.path
    _require(source_path.is_file(), f"{where}: evidence cites missing source file {span.path!r}")
    data = read_bytes(source_path)
    _require(not is_binary(data), f"{where}: evidence cites binary file {span.path!r} (no line spans allowed)")
    try:
        text = decode_strict_utf8(data)
    except SourceDecodeError as exc:
        raise ManifestError(f"{where}: evidence cites non-UTF-8 file {span.path!r} ({exc})") from exc
    line_count = logical_line_count(text)
    _require(span.start_line >= 1, f"{where}: start_line must be >= 1")
    _require(span.end_line >= span.start_line, f"{where}: end_line must be >= start_line")
    _require(
        span.end_line <= line_count,
        f"{where}: end_line {span.end_line} exceeds logical_line_count {line_count} of {span.path!r}",
    )
    if span.granularity == "file":
        _require(
            span.start_line == 1 and span.end_line == line_count,
            f"{where}: file-granularity evidence must span 1..{line_count} of {span.path!r}",
        )


def load_fixture(directory: Path, support_matrix: SupportMatrix) -> LoadedFixture:
    manifest_path = directory / "manifest.json"
    data = _read_json(manifest_path)
    where0 = str(manifest_path)

    if data.get("schemaVersion") != schema.FIXTURE_SCHEMA_VERSION:
        raise ManifestError(f"{where0}: unsupported fixture schema version {data.get('schemaVersion')!r}")
    for forbidden in schema.FORBIDDEN_BLESS_KEYS:
        if data.get(forbidden):
            raise ManifestError(f"{where0}: golden facts must be hand-authored; forbidden key {forbidden!r} present")

    fixture_id = str(data.get("fixtureId", ""))
    _require(bool(fixture_id), f"{where0}: missing 'fixtureId'")
    fixture_class = data.get("fixtureClass")
    _require(fixture_class in schema.FIXTURE_CLASSES, f"{where0}: invalid fixtureClass {fixture_class!r}")
    language = data.get("language")
    _require(language in schema.LANGUAGES, f"{where0}: unsupported language {language!r}")
    revision_identity = data.get("revisionIdentity")
    _require(
        revision_identity in schema.REVISION_IDENTITY_METHODS,
        f"{where0}: unsupported revisionIdentity {revision_identity!r}",
    )

    producer_list = data.get("producerVersionSet")
    _require(isinstance(producer_list, list) and bool(producer_list), f"{where0}: producerVersionSet must be non-empty")
    for producer in producer_list:
        _require(
            isinstance(producer, str) and "@" in producer and not producer.startswith("@") and not producer.endswith("@"),
            f"{where0}: producerVersionSet entry {producer!r} must be 'name@version'",
        )
    producers = set(producer_list)

    constructs_covered = tuple(data.get("constructsCovered", []))
    for construct_id in constructs_covered:
        _require(construct_id in support_matrix, f"{where0}: undeclared support-matrix construct {construct_id!r}")
        _require(
            support_matrix.constructs[construct_id].language in (language, "mixed") or language == "mixed",
            f"{where0}: construct {construct_id!r} language mismatch with fixture language {language!r}",
        )

    expected: list[ExpectedFact] = []
    seen_identities: set[tuple] = set()
    raw_expected = data.get("expected", {})
    for group in schema.FACT_GROUPS:
        for index, raw in enumerate(raw_expected.get(group, [])):
            where = f"{where0} expected.{group}[{index}]"
            _require(isinstance(raw, dict), f"{where}: fact must be an object")
            fact = _build_fact(group, raw, where=where, producers=producers)
            identity = fact.key()
            _require(identity not in seen_identities, f"{where}: duplicate expected identity")
            seen_identities.add(identity)
            fact_constructs = tuple(raw.get("constructs", []))
            for construct_id in fact_constructs:
                _require(construct_id in support_matrix, f"{where}: undeclared construct {construct_id!r}")
            # Provenance: every cited span must resolve in the stored revision.
            for span in fact.evidence:
                _validate_evidence_against_source(directory, span, where=where)
            expected.append(ExpectedFact(group=group, fact=fact, constructs=fact_constructs, raw=raw))

    # Fixtures must actually declare something to measure.
    _require(bool(expected), f"{where0}: fixture declares no expected facts")

    return LoadedFixture(
        fixture_id=fixture_id,
        fixture_class=fixture_class,
        language=language,
        title=str(data.get("title", fixture_id)),
        description=str(data.get("description", "")),
        directory=directory,
        source_root=str(data.get("sourceRoot", ".")),
        revision_identity=revision_identity,
        producer_version_set=tuple(producer_list),
        constructs_covered=constructs_covered,
        deterministic=bool(data.get("deterministic", False)),
        expected=tuple(expected),
    )


def load_corpus(fixtures_dir: Path, support_matrix: SupportMatrix) -> list[LoadedFixture]:
    """Load every fixture under ``fixtures_dir`` in deterministic id order."""

    if not fixtures_dir.is_dir():
        raise ManifestError(f"missing fixtures directory: {fixtures_dir}")
    fixtures: list[LoadedFixture] = []
    seen_ids: set[str] = set()
    for manifest_path in sorted(fixtures_dir.rglob("manifest.json")):
        fixture = load_fixture(manifest_path.parent, support_matrix)
        if fixture.fixture_id in seen_ids:
            raise ManifestError(f"duplicate fixture id {fixture.fixture_id!r} at {manifest_path}")
        seen_ids.add(fixture.fixture_id)
        fixtures.append(fixture)
    fixtures.sort(key=lambda fixture: fixture.fixture_id)
    return fixtures
