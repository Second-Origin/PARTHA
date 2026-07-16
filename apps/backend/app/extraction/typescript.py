from __future__ import annotations

import posixpath

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractionResult,
    RI_SEC_PATH_ESCAPE,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.intelligence import canonical

_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())


class TypeScriptExtractor:
    name = "typescript-ast"
    version = "1.0.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return path.endswith(".ts") or path.endswith(".tsx")

    def _parser(self, path: str) -> Parser:
        return Parser(_TSX_LANGUAGE if path.endswith(".tsx") else _TS_LANGUAGE)

    def extract(self, path: str, source: bytes) -> ExtractionResult:
        text, source_diag = decode_source(path, source, producer=self.producer)
        if text is None:
            return ExtractionResult(diagnostics=(source_diag,))

        try:
            normalized_path = canonical.normalize_repo_path(path)
        except canonical.PathEscapeError:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SEC_PATH_ESCAPE,
                        category="path escape",
                        severity="error",
                        message="source path is absolute or escapes the repository root",
                        path=None,
                    ),
                )
            )

        line_count = logical_line_count(text)
        tree = self._parser(path).parse(source)

        nodes: list[ExtractedNode] = []
        diagnostics: list[ExtractedDiagnostic] = []

        file_key = canonical.normalize_stable_key("file", f"file:{normalized_path}")
        file_ev, file_diag = build_evidence(
            path, 1, line_count, line_count, producer=self.producer, granularity="file"
        )
        if file_ev is not None:
            nodes.append(
                ExtractedNode(
                    node_kind="file",
                    stable_key=file_key,
                    name=posixpath.basename(normalized_path),
                    language="typescript",
                    evidence=(file_ev,),
                )
            )
        elif file_diag is not None:
            diagnostics.append(file_diag)

        # tree is retained for construct queries added in later tasks.
        _ = tree
        return ExtractionResult(nodes=tuple(nodes), diagnostics=tuple(diagnostics))
