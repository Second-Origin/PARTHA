from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


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
