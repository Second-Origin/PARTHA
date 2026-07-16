from __future__ import annotations

import ast
import posixpath

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_SRC_MALFORMED,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.intelligence import canonical


class PythonExtractor:
    name = "python-ast"
    version = "1.0.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(self, path: str, source: bytes) -> ExtractionResult:
        text, source_diag = decode_source(path, source, producer=self.producer)
        if text is None:
            return ExtractionResult(diagnostics=(source_diag,))

        line_count = logical_line_count(text)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SRC_MALFORMED,
                        category="malformed source",
                        severity="error",
                        message="file could not be parsed as Python",
                        path=canonical.normalize_repo_path(path),
                    ),
                )
            )

        nodes: list[ExtractedNode] = []
        observations: list[ExtractedObservation] = []
        diagnostics: list[ExtractedDiagnostic] = []

        module_key = self._module_key(path)
        module_ev, module_ev_diag = build_evidence(
            path, 1, line_count, line_count, producer=self.producer, granularity="file"
        )
        if module_ev is not None:
            nodes.append(
                ExtractedNode(
                    node_kind="module",
                    stable_key=module_key,
                    name=posixpath.basename(canonical.normalize_repo_path(path)),
                    language="python",
                    evidence=(module_ev,),
                )
            )
        elif module_ev_diag is not None:
            diagnostics.append(module_ev_diag)

        self._collect_imports(
            tree, path, line_count, module_key, observations, diagnostics
        )

        return ExtractionResult(
            nodes=tuple(nodes),
            observations=tuple(observations),
            diagnostics=tuple(diagnostics),
        )

    def _module_key(self, path: str) -> str:
        directory = posixpath.dirname(canonical.normalize_repo_path(path))
        return canonical.normalize_stable_key("module", f"mod:{directory}")

    def _collect_imports(
        self, tree, path, line_count, module_key, observations, diagnostics
    ) -> None:
        ordinal = 0
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                names = [
                    f"{base}.{alias.name}" if base else alias.name
                    for alias in node.names
                    if alias.name != "*"
                ]
            else:
                continue
            for name in names:
                ordinal += 1
                ev, diag = build_evidence(
                    path, node.lineno, node.end_lineno or node.lineno, line_count,
                    producer=self.producer,
                )
                if ev is None:
                    if diag is not None:
                        diagnostics.append(diag)
                    continue
                observations.append(
                    ExtractedObservation(
                        observed_kind="import",
                        subject_kind="module",
                        subject_key=module_key,
                        referent_text=name,
                        ordinal=ordinal,
                        evidence=ev,
                    )
                )
