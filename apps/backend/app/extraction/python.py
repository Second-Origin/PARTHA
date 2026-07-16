from __future__ import annotations

import ast
import posixpath

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_EXT_UNSUPPORTED,
    RI_KEY_DUP_SYMBOL,
    RI_SEC_PATH_ESCAPE,
    RI_SRC_MALFORMED,
    assign_ordinals,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.extraction.naming import (
    DiscriminatorAssigner,
    module_name,
    module_stable_key,
    symbol_stable_key,
)
from app.intelligence import canonical

_ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
_DYNAMIC_IMPORT_CALLS = {"import_module", "__import__"}
_REFLECTION_CALLS = {"getattr", "setattr", "delattr"}

# Collectors emit this; assign_ordinals sets the RFC §6.4 value on the way out.
# It is deliberately invalid (ordinals are one-based) so a result that skipped
# assignment fails loudly rather than persisting a wrong identity.
_UNASSIGNED_ORDINAL = 0


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

        module_key = module_stable_key(path)
        module_ev, module_ev_diag = build_evidence(
            path, 1, line_count, line_count, producer=self.producer, granularity="file"
        )
        if module_ev is not None:
            nodes.append(
                ExtractedNode(
                    node_kind="module",
                    stable_key=module_key,
                    name=module_name(path),
                    # A module is a directory, and a directory can hold more than
                    # one language. Its record must be language-neutral or the
                    # Python and TypeScript extractors emit conflicting records
                    # for one key and the snapshot refuses to seal.
                    language=None,
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
        self._collect_blind_spots(tree, path, line_count, diagnostics)

        return ExtractionResult(
            nodes=tuple(nodes),
            observations=assign_ordinals(observations),
            diagnostics=tuple(diagnostics),
        )

    def _collect_imports(
        self, tree, path, line_count, module_key, observations, diagnostics
    ) -> None:
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
                        ordinal=_UNASSIGNED_ORDINAL,
                        evidence=ev,
                    )
                )

    _DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def _collect_symbols(
        self, tree, path, line_count, nodes, observations, diagnostics
    ) -> None:
        assigner = DiscriminatorAssigner()

        def visit(scope: list[str], body) -> None:
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
                    decorator_nodes = [
                        (self._decorator_name(d), d)
                        for d in getattr(child, "decorator_list", [])
                    ]
                    decorator_nodes = [(n, d) for n, d in decorator_nodes if n]
                    decorators = [n for n, _ in decorator_nodes]
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
                    observations.append(
                        ExtractedObservation(
                            observed_kind="definition",
                            subject_kind="symbol",
                            subject_key=canonical.normalize_stable_key("symbol", final_key),
                            referent_text=None,
                            ordinal=_UNASSIGNED_ORDINAL,
                            evidence=ev,
                        )
                    )
                    # A decorator sits above `def`/`class`, so it is outside the
                    # symbol's own span. Give each one provenance for its source
                    # lines rather than only a name in `properties` (#90).
                    for decorator_name, decorator_node in decorator_nodes:
                        dec_ev, dec_diag = build_evidence(
                            path, decorator_node.lineno,
                            decorator_node.end_lineno or decorator_node.lineno,
                            line_count, producer=self.producer,
                        )
                        if dec_ev is None:
                            if dec_diag is not None:
                                diagnostics.append(dec_diag)
                            continue
                        observations.append(
                            ExtractedObservation(
                                observed_kind="decorator",
                                subject_kind="symbol",
                                subject_key=canonical.normalize_stable_key("symbol", final_key),
                                referent_text=decorator_name,
                                ordinal=_UNASSIGNED_ORDINAL,
                                evidence=dec_ev,
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
                        observations.append(
                            ExtractedObservation(
                                observed_kind="route",
                                subject_kind="symbol",
                                subject_key=canonical.normalize_stable_key("symbol", final_key),
                                referent_text=route_path,
                                ordinal=_UNASSIGNED_ORDINAL,
                                evidence=route_ev,
                            )
                        )
                if duplicate:
                    diagnostics.append(
                        ExtractedDiagnostic(
                            code=RI_KEY_DUP_SYMBOL,
                            category="duplicate symbol",
                            severity="info",
                            # The key lives in `subject`, the field meant for it;
                            # repeating it here would put source-derived text in
                            # `message`, which RFC §13 reserves from content.
                            message="duplicate symbol name resolved with a discriminator",
                            path=canonical.normalize_repo_path(path),
                            subject=canonical.normalize_stable_key("symbol", final_key),
                        )
                    )
                visit([*scope, child.name], child.body)

        visit([], tree.body)

    def _imported_bindings(self, tree) -> set[str]:
        """Names this file binds via an import.

        ``import os`` binds ``os``; ``import os.path`` binds the top package
        ``os``; ``import numpy as np`` binds ``np``; ``from m import Thing``
        binds ``Thing``. These are the names whose attributes belong to somebody
        else, which is what makes rebinding them monkey-patching.
        """

        bindings: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bindings.add(alias.asname or alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        bindings.add(alias.asname or alias.name)
        return bindings

    def _attribute_root(self, node):
        """Resolve ``a.b.c`` to its root ``Name``, or None if not name-rooted."""

        while isinstance(node, ast.Attribute):
            node = node.value
        return node if isinstance(node, ast.Name) else None

    def _collect_blind_spots(self, tree, path, line_count, diagnostics) -> None:
        normalized = canonical.normalize_repo_path(path)
        imported = self._imported_bindings(tree)

        def flag(node, message: str) -> None:
            # `message` names the construct; it never quotes source. Diagnostics
            # are stored and surfaced, and RFC §13 forbids embedding repository
            # content or secrets in `message`/`details` — the path and span
            # already say exactly where to look.
            diagnostics.append(
                ExtractedDiagnostic(
                    code=RI_EXT_UNSUPPORTED,
                    category="unsupported construct",
                    severity="info",
                    message=message,
                    path=normalized,
                    span=(node.lineno, node.end_lineno or node.lineno),
                )
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                flag(node, "star-import is unsupported")
            elif isinstance(node, ast.ClassDef) and any(
                keyword.arg == "metaclass" for keyword in node.keywords
            ):
                # The class itself is still extracted; what a metaclass does to it
                # at runtime is not modelled, so say so rather than imply we know.
                flag(node, "metaclass is unsupported")
            elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                # Rebinding an attribute on a name this file imported mutates an
                # object defined elsewhere, so any fact stated about that object's
                # definition is incomplete. Assignment to a local or to `self` is
                # ordinary and must not be flagged, or the diagnostic is noise.
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if not isinstance(target, ast.Attribute):
                        continue
                    root = self._attribute_root(target)
                    if root is not None and root.id in imported:
                        flag(node, "monkey-patching an imported name is unsupported")
                        break
            elif isinstance(node, ast.Call):
                func = node.func
                # These names come from this module's own closed vocabulary, not
                # from arbitrary source text, so naming them leaks nothing.
                if isinstance(func, ast.Name) and func.id in _REFLECTION_CALLS:
                    flag(node, f"reflection via {func.id}() is unsupported")
                elif isinstance(func, ast.Name) and func.id in _DYNAMIC_IMPORT_CALLS:
                    flag(node, f"dynamic import via {func.id}() is unsupported")
                elif isinstance(func, ast.Attribute) and func.attr in _DYNAMIC_IMPORT_CALLS:
                    flag(node, f"dynamic import via {func.attr}() is unsupported")

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
