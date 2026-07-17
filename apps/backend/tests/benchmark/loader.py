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
from typing import Any, Mapping

from app.extraction.support_matrix import SUPPORT_MATRIX as PRODUCTION_SUPPORT_MATRIX
from app.intelligence import canonical

from benchmark import schema
from benchmark.facts import EvidenceSpan, Fact, canonical_value
from benchmark.sourcefiles import (
    SourceDecodeError,
    decode_strict_utf8,
    is_binary,
    logical_line_count,
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
    matrix_language: str
    matrix_construct: str


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
    mappings = data.get("productionMappings")
    if not isinstance(mappings, dict) or set(mappings) != set(raw):
        raise ManifestError(
            f"{path}: productionMappings must map every benchmark construct exactly once"
        )
    covered_production: set[tuple[str, str]] = set()
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
        mapping = mappings[construct_id]
        matrix_language = str(mapping.get("language", ""))
        matrix_construct = str(mapping.get("construct", ""))
        if matrix_language not in PRODUCTION_SUPPORT_MATRIX:
            raise ManifestError(
                f"{path}: construct {construct_id!r} maps to unknown production matrix {matrix_language!r}"
            )
        production = PRODUCTION_SUPPORT_MATRIX[matrix_language]
        production_supported = matrix_construct in production.supported
        production_unsupported = matrix_construct in production.unsupported
        if not (production_supported or production_unsupported):
            raise ManifestError(
                f"{path}: construct {construct_id!r} maps to unknown production construct "
                f"{matrix_language}.{matrix_construct}"
            )
        if supported != production_supported:
            raise ManifestError(
                f"{path}: construct {construct_id!r} support status disagrees with "
                f"{matrix_language}.{matrix_construct}"
            )
        covered_production.add((matrix_language, matrix_construct))
        constructs[construct_id] = ConstructSpec(
            construct_id=construct_id,
            language=language,
            supported=supported,
            description=str(spec.get("description", "")),
            expected_diagnostic=expected_diagnostic,
            matrix_language=matrix_language,
            matrix_construct=matrix_construct,
        )
    missing_production = sorted(
        (language, construct)
        for language, matrix in PRODUCTION_SUPPORT_MATRIX.items()
        for construct in (*matrix.supported, *matrix.unsupported)
        if (language, construct) not in covered_production
    )
    if missing_production:
        raise ManifestError(
            f"{path}: production support constructs have no benchmark mapping: {missing_production}"
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


def _fixture_source_files(
    directory: Path,
    synthetic_files: tuple[tuple[str, bytes], ...] = (),
) -> dict[str, bytes]:
    """Return physical and manifest-declared source bytes in stable path order."""

    files: dict[str, bytes] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative = path.relative_to(directory).as_posix()
        files[relative] = path.read_bytes()
    for path, content in synthetic_files:
        files[path] = content
    return {path: files[path] for path in sorted(files)}


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
    max_source_bytes: int = 512 * 1024
    synthetic_files: tuple[tuple[str, bytes], ...] = ()

    def source_files(self) -> dict[str, bytes]:
        """Every stored byte of the synthetic repository (everything but the manifest)."""

        return _fixture_source_files(self.directory, self.synthetic_files)

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
            value=canonical_value(raw.get("properties")) if raw.get("properties") is not None else "",
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
            ordinal=int(raw.get("ordinal", 1)),
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
            {
                "details": raw.get("details"),
                "path": normalized_path,
                "span": {"startLine": span["startLine"], "endLine": span["endLine"]} if span else None,
            }
        )
        return Fact(
            fact_type="diagnostic",
            kind=code,
            subject=str(raw.get("subject", "")),
            object=str(raw.get("object", "")),
            severity=severity,
            category=str(raw.get("category", "")),
            message=str(raw.get("message", "")),
            producer=producer,
            value=location,
        )
    raise ManifestError(f"{where}: unknown fact group {group!r}")


def _validate_evidence_against_source(
    sources: Mapping[str, bytes], span: EvidenceSpan, *, where: str
) -> None:
    """Enforce RFC-0001 §6.2: the cited file exists, decodes, and the span is in range."""

    data = sources.get(span.path)
    _require(data is not None, f"{where}: evidence cites missing source file {span.path!r}")
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


def _load_synthetic_files(data: dict[str, Any], *, where: str, directory: Path) -> tuple[tuple[str, bytes], ...]:
    """Validate manifest-declared UTF-8 sources without normalizing their raw paths."""

    raw_files = data.get(schema.SYNTHETIC_FILES_FIELD, {})
    _require(
        isinstance(raw_files, dict),
        f"{where}: {schema.SYNTHETIC_FILES_FIELD} must be an object mapping paths to UTF-8 content",
    )
    physical_paths = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    synthetic_files: list[tuple[str, bytes]] = []
    for raw_path, content in sorted(raw_files.items()):
        _require(
            isinstance(raw_path, str) and raw_path and raw_path != "manifest.json",
            f"{where}: synthetic source path must be a non-empty non-manifest string",
        )
        _require(isinstance(content, str), f"{where}: synthetic source {raw_path!r} must be UTF-8 text")
        _require(raw_path not in physical_paths, f"{where}: synthetic source {raw_path!r} duplicates a stored file")
        try:
            encoded = content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ManifestError(f"{where}: synthetic source {raw_path!r} is not UTF-8 encodable") from exc
        synthetic_files.append((raw_path, encoded))
    return tuple(synthetic_files)


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
    synthetic_files = _load_synthetic_files(data, where=where0, directory=directory)
    sources = _fixture_source_files(directory, synthetic_files)

    constructs_covered = tuple(data.get("constructsCovered", []))
    max_source_bytes = data.get("maxSourceBytes", 512 * 1024)
    _require(
        isinstance(max_source_bytes, int) and max_source_bytes >= 1,
        f"{where0}: maxSourceBytes must be a positive integer",
    )
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
                _validate_evidence_against_source(sources, span, where=where)
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
        max_source_bytes=max_source_bytes,
        synthetic_files=synthetic_files,
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
