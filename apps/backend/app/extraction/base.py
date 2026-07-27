from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from app.intelligence import canonical


@dataclass(frozen=True)
class ExtractedEvidence:
    path: str  # repository-relative POSIX, normalized (RFC §4.2)
    start_line: int  # one-based
    end_line: int  # one-based, inclusive
    logical_line_count: int
    granularity: str = "span"  # "span" | "file"


@dataclass(frozen=True)
class ExtractedNode:
    node_kind: str  # "file" | "module" | "symbol" | "dependency"
    stable_key: str  # normalized per RFC §4.3
    name: str | None
    language: str | None
    evidence: tuple[ExtractedEvidence, ...]
    properties: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ExtractedObservation:
    observed_kind: str  # "definition" | "import" | "call" | "route" | ...
    subject_kind: str
    subject_key: str
    referent_text: str | None
    ordinal: int
    evidence: ExtractedEvidence


@dataclass(frozen=True)
class ExtractedDiagnostic:
    code: str
    category: str
    severity: str  # fatal | error | warning | info
    message: str
    path: str | None = None
    span: tuple[int, int] | None = None
    subject: str | None = None
    details: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ExtractionResult:
    nodes: tuple[ExtractedNode, ...] = ()
    observations: tuple[ExtractedObservation, ...] = ()
    diagnostics: tuple[ExtractedDiagnostic, ...] = ()


@runtime_checkable
class Extractor(Protocol):
    name: str
    version: str

    def supports(self, path: str) -> bool: ...

    def extract(self, path: str, source: bytes) -> ExtractionResult: ...


# --- Diagnostic codes (RFC §8.2) -------------------------------------------

RI_SRC_BINARY = "RI-SRC-BINARY"
RI_SRC_MALFORMED = "RI-SRC-MALFORMED"
RI_EXT_UNSUPPORTED = "RI-EXT-UNSUPPORTED"
RI_LIMIT_SKIP = "RI-LIMIT-SKIP"
RI_SPAN_INVALID = "RI-SPAN-INVALID"
RI_SEC_PATH_ESCAPE = "RI-SEC-PATH-ESCAPE"
RI_KEY_DUP_SYMBOL = "RI-KEY-DUP-SYMBOL"

_CATEGORY = {
    RI_SRC_BINARY: "binary source",
    RI_SRC_MALFORMED: "malformed source",
    RI_EXT_UNSUPPORTED: "unsupported construct",
    RI_LIMIT_SKIP: "resource-limit skip",
    RI_SPAN_INVALID: "invalid span",
    RI_SEC_PATH_ESCAPE: "path escape",
    RI_KEY_DUP_SYMBOL: "duplicate symbol",
}


def assign_ordinals(
    observations: Sequence[ExtractedObservation],
) -> tuple[ExtractedObservation, ...]:
    """Set RFC §6.4 ordinals: source order among otherwise-identical observations.

    ``ordinal`` exists to separate observations whose *other* identity fields are
    all equal — two identical occurrences on one line, while columns are deferred.
    It is deliberately not a file-wide counter: observations that already differ
    in kind, subject, referent text, or span are distinct without it and each
    start at 1.

    Collectors emit a placeholder ordinal; this is the single authority that sets
    the real value, so the grouping key here stays in lockstep with the identity
    document that ``canonical.compute_observation_id`` hashes.
    """

    counts: dict[tuple[object, ...], int] = defaultdict(int)
    assigned: list[ExtractedObservation] = []
    for observation in observations:
        identity = (
            observation.observed_kind,
            observation.subject_kind,
            observation.subject_key,
            observation.referent_text,
            observation.evidence.path,
            observation.evidence.start_line,
            observation.evidence.end_line,
        )
        counts[identity] += 1
        assigned.append(replace(observation, ordinal=counts[identity]))
    return tuple(assigned)


def logical_line_count(text: str) -> int:
    """RFC §6.2: one logical line per file, plus one per U+000A."""

    return 1 + text.count("\n")


def decode_source(path: str, source: bytes, *, producer: str) -> tuple[str | None, ExtractedDiagnostic | None]:
    """Strict UTF-8 decode with RFC §6.2 binary/malformed handling.

    Returns ``(text, None)`` for decodable text (a zero-byte file decodes to
    ``""``), or ``(None, diagnostic)`` when the file is binary (contains a NUL
    byte) or is not valid UTF-8.
    """

    try:
        normalized_path = canonical.normalize_repo_path(path)
        subject = canonical.normalize_stable_key("file", f"file:{normalized_path}")
    except canonical.PathEscapeError:
        normalized_path = None
        subject = None

    if b"\x00" in source:
        return None, ExtractedDiagnostic(
            code=RI_SRC_BINARY,
            category=_CATEGORY[RI_SRC_BINARY],
            severity="info",
            message="file contains a NUL byte and is excluded from line-addressed extraction",
            path=normalized_path,
            subject=subject,
        )
    try:
        return source.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, ExtractedDiagnostic(
            code=RI_SRC_MALFORMED,
            category=_CATEGORY[RI_SRC_MALFORMED],
            severity="error",
            message="file is not valid UTF-8 and could not be decoded",
            path=normalized_path,
            subject=subject,
        )


def build_evidence(
    path: str,
    start_line: int,
    end_line: int,
    logical_line_count: int,
    *,
    producer: str,
    granularity: str = "span",
) -> tuple[ExtractedEvidence | None, ExtractedDiagnostic | None]:
    """Validate a span and path (RFC §4.2, §6.2), returning evidence or a diagnostic.

    ``producer`` is the emitting extractor's ``name@version`` identifier. It is
    accepted for call-site uniformity across extractors; the diagnostic's producer
    is recorded when the extraction result is persisted to the snapshot store, not
    embedded in the returned ``ExtractedDiagnostic`` here.
    """

    try:
        normalized = canonical.normalize_repo_path(path)
    except canonical.PathEscapeError:
        return None, ExtractedDiagnostic(
            code=RI_SEC_PATH_ESCAPE,
            category=_CATEGORY[RI_SEC_PATH_ESCAPE],
            severity="error",
            message="evidence path is absolute or escapes the repository root",
            path=None,
        )
    if not (1 <= start_line <= end_line <= logical_line_count):
        return None, ExtractedDiagnostic(
            code=RI_SPAN_INVALID,
            category=_CATEGORY[RI_SPAN_INVALID],
            severity="error",
            message=(f"span {start_line}..{end_line} is not within 1..{logical_line_count}"),
            path=normalized,
            span=(start_line, end_line),
        )
    return (
        ExtractedEvidence(
            path=normalized,
            start_line=start_line,
            end_line=end_line,
            logical_line_count=logical_line_count,
            granularity=granularity,
        ),
        None,
    )
