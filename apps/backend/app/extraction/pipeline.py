"""Repository-level source policy and real extractor dispatch.

This module is the production boundary that turns a stored repository revision
into extractor runs.  It does not parse source: Python and TypeScript parsing is
delegated exclusively to their real :class:`Extractor` implementations.  The
pipeline owns the repository-wide concerns that no single language extractor
can own: inventory nodes, the mandatory repository root, path normalization,
and the output-affecting file-size budget required by RFC-0001 sections 4.3,
6.2, 8.2, and 12.7.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedEvidence,
    ExtractedNode,
    ExtractionResult,
    Extractor,
    RI_LIMIT_SKIP,
    RI_SEC_PATH_ESCAPE,
    decode_source,
    logical_line_count,
)
from app.intelligence import canonical

DEFAULT_MAX_SOURCE_BYTES = 512 * 1024


@dataclass(frozen=True)
class ProducedExtraction:
    """One result plus the exact producer identity that emitted it."""

    producer_name: str
    producer_version: str
    result: ExtractionResult

    @property
    def producer(self) -> str:
        return f"{self.producer_name}@{self.producer_version}"


class ExtractionPipeline:
    """Apply repository policy, then dispatch stored bytes to real extractors."""

    inventory_name = "repository-inventory"
    inventory_version = "1.1.0"

    def __init__(
        self,
        extractors: Sequence[Extractor],
        *,
        max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    ) -> None:
        if max_source_bytes < 1:
            raise ValueError("max_source_bytes must be at least 1")
        self.extractors = tuple(extractors)
        self.max_source_bytes = max_source_bytes

    def run(
        self,
        sources: Mapping[str, bytes],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> tuple[ProducedExtraction, ...]:
        inventory_nodes: list[ExtractedNode] = []
        inventory_diagnostics: list[ExtractedDiagnostic] = []
        produced: list[ProducedExtraction] = []
        repository_evidence: ExtractedEvidence | None = None

        for raw_path, source in sorted(sources.items()):
            if check_cancelled is not None:
                check_cancelled()
            try:
                path = canonical.normalize_repo_path(raw_path)
            except canonical.PathEscapeError:
                inventory_diagnostics.append(
                    ExtractedDiagnostic(
                        code=RI_SEC_PATH_ESCAPE,
                        category="path escape",
                        severity="error",
                        message="source path is absolute or escapes the repository root",
                    )
                )
                continue

            # The mandatory repository entity is an observed fact, so it needs
            # valid stored-source evidence even when language extraction later
            # reports a non-fatal diagnostic and emits no file-level facts.
            # Establish that evidence before the parser and size-policy branches
            # to keep a diagnostics-only text repository sealable.
            if repository_evidence is None:
                evidence = self._whole_file_evidence(path, source)
                if evidence is not None:
                    repository_evidence = self._repo_evidence(evidence)

            file_key = canonical.normalize_stable_key("file", f"file:{path}")
            if len(source) > self.max_source_bytes:
                inventory_diagnostics.append(
                    ExtractedDiagnostic(
                        code=RI_LIMIT_SKIP,
                        category="resource-limit skip",
                        severity="info",
                        message="file exceeds the configured source-size budget",
                        path=path,
                        subject=file_key,
                        details={
                            "budgetBytes": self.max_source_bytes,
                            "reportedBytes": len(source),
                        },
                    )
                )
                continue

            matches = [extractor for extractor in self.extractors if extractor.supports(path)]
            if len(matches) > 1:
                raise ValueError(f"multiple extractors support {path!r}")

            if matches:
                extractor = matches[0]
                result = extractor.extract(path, source)
                if check_cancelled is not None:
                    check_cancelled()
                produced.append(
                    ProducedExtraction(extractor.name, extractor.version, result)
                )
                # Python emits a directory module but no file node. Inventory
                # supplies that shared entity only after successful extraction;
                # TypeScript already emits its own file node.
                if result.nodes and not any(
                    node.node_kind == "file" and node.stable_key == file_key
                    for node in result.nodes
                ):
                    evidence = self._whole_file_evidence(path, source)
                    if evidence is not None:
                        inventory_nodes.append(
                            self._file_node(path, evidence, self._language(path), source)
                        )
                continue

            text, diagnostic = decode_source(
                path,
                source,
                producer=f"{self.inventory_name}@{self.inventory_version}",
            )
            if diagnostic is not None:
                inventory_diagnostics.append(
                    ExtractedDiagnostic(
                        code=diagnostic.code,
                        category=diagnostic.category,
                        severity=diagnostic.severity,
                        message=diagnostic.message,
                        path=diagnostic.path,
                        span=diagnostic.span,
                        subject=file_key,
                        details=diagnostic.details,
                    )
                )
                continue
            assert text is not None
            evidence = ExtractedEvidence(
                path=path,
                start_line=1,
                end_line=logical_line_count(text),
                logical_line_count=logical_line_count(text),
                granularity="file",
            )
            inventory_nodes.append(self._file_node(path, evidence, self._language(path), source))

        if repository_evidence is not None:
            inventory_nodes.insert(
                0,
                ExtractedNode(
                    node_kind="repository",
                    stable_key="repo:root",
                    name="repository",
                    language=None,
                    evidence=(repository_evidence,),
                ),
            )

        if inventory_nodes or inventory_diagnostics:
            produced.insert(
                0,
                ProducedExtraction(
                    self.inventory_name,
                    self.inventory_version,
                    ExtractionResult(
                        nodes=tuple(inventory_nodes),
                        diagnostics=tuple(inventory_diagnostics),
                    ),
                ),
            )
        return tuple(produced)

    def _whole_file_evidence(
        self, path: str, source: bytes
    ) -> ExtractedEvidence | None:
        text, _ = decode_source(
            path,
            source,
            producer=f"{self.inventory_name}@{self.inventory_version}",
        )
        if text is None:
            return None
        count = logical_line_count(text)
        return ExtractedEvidence(path, 1, count, count, "file")

    @staticmethod
    def _repo_evidence(evidence: ExtractedEvidence) -> ExtractedEvidence:
        return ExtractedEvidence(
            path=evidence.path,
            start_line=1,
            end_line=1,
            logical_line_count=evidence.logical_line_count,
            granularity="span",
        )

    @staticmethod
    def _language(path: str) -> str | None:
        if path.endswith(".py"):
            return "python"
        if path.endswith((".ts", ".tsx")):
            return "typescript"
        return None

    @staticmethod
    def _file_node(
        path: str,
        evidence: ExtractedEvidence,
        language: str | None,
        source: bytes,
    ) -> ExtractedNode:
        return ExtractedNode(
            node_kind="file",
            stable_key=canonical.normalize_stable_key("file", f"file:{path}"),
            name=posixpath.basename(path),
            language=language,
            evidence=(evidence,),
            properties={"content_sha256": canonical.sha256_prefixed(source)},
        )
