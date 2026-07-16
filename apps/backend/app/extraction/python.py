from __future__ import annotations

import ast
import posixpath

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_KEY_DUP_SYMBOL,
    RI_SEC_PATH_ESCAPE,
    RI_SRC_MALFORMED,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.extraction.naming import DiscriminatorAssigner, symbol_stable_key
from app.intelligence import canonical

_ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


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

        try:
            canonical.normalize_repo_path(path)
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
        self._collect_symbols(
            tree, path, line_count, nodes, observations, diagnostics
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
                level_prefix = "." * node.level
                base = node.module or ""
                names = [
                    f"{level_prefix}{base}.{alias.name}" if base else f"{level_prefix}{alias.name}"
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

    _DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def _collect_symbols(
        self, tree, path, line_count, nodes, observations, diagnostics
    ) -> None:
        assigner = DiscriminatorAssigner()
        ordinal = 0

        def visit(scope: list[str], body) -> None:
            nonlocal ordinal
            for child in body:
                if not isinstance(child, self._DEF_TYPES):
                    continue
                base_key = symbol_stable_key(path, scope, child.name)
                final_key, duplicate = assigner.key(base_key)
                ev, diag = build_evidence(
                    path, child.lineno, child.end_lineno or child.lineno,
                    line_count, producer=self.producer,
                )
                if ev is None:
                    if diag is not None:
                        diagnostics.append(diag)
                else:
                    decorators = [self._decorator_name(d) for d in getattr(child, "decorator_list", [])]
                    decorators = [d for d in decorators if d]
                    properties = {"decorators": decorators} if decorators else None
                    nodes.append(
                        ExtractedNode(
                            node_kind="symbol",
                            stable_key=canonical.normalize_stable_key("symbol", final_key),
                            name=child.name,
                            language="python",
                            evidence=(ev,),
                            properties=properties,
                        )
                    )
                    ordinal += 1
                    observations.append(
                        ExtractedObservation(
                            observed_kind="definition",
                            subject_kind="symbol",
                            subject_key=canonical.normalize_stable_key("symbol", final_key),
                            referent_text=None,
                            ordinal=ordinal,
                            evidence=ev,
                        )
                    )
                    for route_path, route_node in self._route_paths(child):
                        route_ev, route_diag = build_evidence(
                            path, route_node.lineno, route_node.end_lineno or route_node.lineno,
                            line_count, producer=self.producer,
                        )
                        if route_ev is None:
                            if route_diag is not None:
                                diagnostics.append(route_diag)
                            continue
                        ordinal += 1
                        observations.append(
                            ExtractedObservation(
                                observed_kind="route",
                                subject_kind="symbol",
                                subject_key=canonical.normalize_stable_key("symbol", final_key),
                                referent_text=route_path,
                                ordinal=ordinal,
                                evidence=route_ev,
                            )
                        )
                if duplicate:
                    diagnostics.append(
                        ExtractedDiagnostic(
                            code=RI_KEY_DUP_SYMBOL,
                            category="duplicate symbol",
                            severity="info",
                            message=f"duplicate symbol name resolved with a discriminator: {final_key}",
                            path=canonical.normalize_repo_path(path),
                            subject=canonical.normalize_stable_key("symbol", final_key),
                        )
                    )
                visit([*scope, child.name], child.body)

        visit([], tree.body)

    def _decorator_name(self, decorator) -> str | None:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        parts: list[str] = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        return ".".join(reversed(parts)) if parts else None

    def _route_paths(self, symbol):
        for decorator in getattr(symbol, "decorator_list", []):
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr not in _ROUTE_METHODS:
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                yield decorator.args[0].value, decorator
