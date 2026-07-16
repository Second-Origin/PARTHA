from __future__ import annotations

import posixpath

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_KEY_DUP_SYMBOL,
    RI_SEC_PATH_ESCAPE,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.extraction.naming import DiscriminatorAssigner, symbol_stable_key
from app.intelligence import canonical

_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())

_NAMED_DECLARATIONS = {
    "function_declaration": "name",
    "function_signature": "name",              # ambient/overload signatures (no body)
    "generator_function_declaration": "name",
    "class_declaration": "name",
    "abstract_class_declaration": "name",
    "interface_declaration": "name",
    "type_alias_declaration": "name",
    "enum_declaration": "name",
    "method_definition": "name",               # emitted via the unified path, in class scope
}


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

        observations: list[ExtractedObservation] = []
        self._collect_symbols(
            tree.root_node, path, line_count, file_key, nodes, observations, diagnostics
        )
        self._collect_imports(tree.root_node, path, line_count, file_key, observations)
        self._collect_routes(tree.root_node, path, line_count, file_key, observations)
        return ExtractionResult(
            nodes=tuple(nodes),
            observations=tuple(observations),
            diagnostics=tuple(diagnostics),
        )

    def _collect_imports(self, root, path, line_count, file_key, observations) -> None:
        source = root.text
        ordinal = len(observations)

        def walk(node):
            nonlocal ordinal
            if node.type in ("import_statement", "export_statement"):
                source_node = node.child_by_field_name("source")
                if source_node is not None:
                    literal = self._node_text(source_node, source).strip("'\"`")
                    ev, _ = build_evidence(
                        path, node.start_point[0] + 1, node.end_point[0] + 1,
                        line_count, producer=self.producer,
                    )
                    if ev is not None:
                        ordinal += 1
                        observations.append(
                            ExtractedObservation(
                                observed_kind="import", subject_kind="file",
                                subject_key=file_key, referent_text=literal,
                                ordinal=ordinal, evidence=ev,
                            )
                        )
            for child in node.named_children:
                walk(child)

        walk(root)

    def _collect_routes(self, root, path, line_count, file_key, observations) -> None:
        source = root.text
        ordinal = len(observations)

        def emit(node, literal):
            nonlocal ordinal
            ev, _ = build_evidence(
                path, node.start_point[0] + 1, node.end_point[0] + 1,
                line_count, producer=self.producer,
            )
            if ev is not None:
                ordinal += 1
                observations.append(
                    ExtractedObservation(
                        observed_kind="route", subject_kind="file",
                        subject_key=file_key, referent_text=literal,
                        ordinal=ordinal, evidence=ev,
                    )
                )

        def walk(node):
            if node.type == "pair":
                key = node.child_by_field_name("key")
                value = node.child_by_field_name("value")
                if (key is not None and value is not None
                        and self._node_text(key, source).strip("'\"") == "path"
                        and value.type in ("string",)):
                    emit(node, self._node_text(value, source).strip("'\"`"))
            elif node.type == "jsx_attribute":
                children = node.named_children
                if children and self._node_text(children[0], source) == "path" and len(children) > 1:
                    literal = self._node_text(children[1], source).strip("'\"{}`")
                    emit(node, literal)
            for child in node.named_children:
                walk(child)

        walk(root)

    def _node_text(self, node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _is_exported(self, node) -> bool:
        return node.parent is not None and node.parent.type == "export_statement"

    def _is_top_level(self, node) -> bool:
        parent = node.parent
        if parent is None:
            return False
        if parent.type == "program":
            return True
        return (
            parent.type == "export_statement"
            and parent.parent is not None
            and parent.parent.type == "program"
        )

    def _collect_symbols(
        self, root, path, line_count, file_key, nodes, observations, diagnostics
    ) -> None:
        assigner = DiscriminatorAssigner()
        source = root.text  # bytes of the whole tree
        counter = {"n": 0}  # mutable box so the one running ordinal is shared

        def emit(name_node, decl_node, scope, exported):
            """Emit one symbol node + its definition observation; return the name."""
            name = self._node_text(name_node, source)
            base_key = symbol_stable_key(path, scope, name)
            final_key, duplicate = assigner.key(base_key)
            key = canonical.normalize_stable_key("symbol", final_key)
            # tree-sitter rows are 0-based; RFC spans are 1-based inclusive.
            ev, diag = build_evidence(
                path, decl_node.start_point[0] + 1, decl_node.end_point[0] + 1,
                line_count, producer=self.producer,
            )
            if ev is None:
                if diag is not None:
                    diagnostics.append(diag)
                return None
            counter["n"] += 1
            nodes.append(
                ExtractedNode(
                    node_kind="symbol", stable_key=key, name=name,
                    language="typescript", evidence=(ev,),
                    properties={"exported": True} if exported else None,
                )
            )
            observations.append(
                ExtractedObservation(
                    observed_kind="definition", subject_kind="symbol",
                    subject_key=key, referent_text=None, ordinal=counter["n"], evidence=ev,
                )
            )
            if duplicate:
                diagnostics.append(
                    ExtractedDiagnostic(
                        code=RI_KEY_DUP_SYMBOL, category="duplicate symbol",
                        severity="info",
                        message=f"duplicate symbol name resolved with a discriminator: {final_key}",
                        path=canonical.normalize_repo_path(path), subject=key,
                    )
                )
            return name

        def visit(node, scope):
            # Top-level const/let/var bindings become symbols (RFC §4.3). Their
            # initializer expressions are intentionally not descended into here;
            # route literals inside them are found by the separate route pass.
            if node.type == "lexical_declaration":
                if self._is_top_level(node):
                    exported = self._is_exported(node)
                    for declarator in node.named_children:
                        if declarator.type != "variable_declarator":
                            continue
                        name_node = declarator.child_by_field_name("name")
                        if name_node is not None and name_node.type == "identifier":
                            emit(name_node, declarator, scope, exported)
                return

            child_scope = scope
            field = _NAMED_DECLARATIONS.get(node.type)
            if field is not None:
                name_node = node.child_by_field_name(field)
                if name_node is not None:
                    # A method_definition arrives here with its enclosing class
                    # already in `scope`, so the unified path qualifies it as
                    # Class.method with no special-casing.
                    emitted = emit(name_node, node, scope, self._is_exported(node))
                    if emitted is not None:
                        child_scope = [*scope, emitted]

            for child in node.named_children:
                visit(child, child_scope)

        visit(root, [])
