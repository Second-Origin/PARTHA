from __future__ import annotations

import posixpath

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

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

_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())

# react-router data-router factories: same call shape, same route-table argument.
_ROUTER_FACTORIES = {"createBrowserRouter", "createHashRouter", "createMemoryRouter"}
_ROUTE_ELEMENTS = {"Route"}

# Collectors emit this; assign_ordinals sets the RFC §6.4 value on the way out.
# It is deliberately invalid (ordinals are one-based) so a result that skipped
# assignment fails loudly rather than persisting a wrong identity.
_UNASSIGNED_ORDINAL = 0

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

        if tree.root_node.has_error:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SRC_MALFORMED,
                        category="malformed source",
                        severity="error",
                        message="file has TypeScript syntax errors",
                        path=normalized_path,
                        subject=file_key,
                    ),
                )
            )

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
            # #89 requires module nodes as well as file nodes. The module is
            # directory-scoped and shared by every file in that directory —
            # including files of another language, so the record carries no
            # language of its own (see the Python extractor's module node).
            nodes.append(
                ExtractedNode(
                    node_kind="module",
                    stable_key=module_stable_key(path),
                    name=module_name(path),
                    language=None,
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
        self._collect_blind_spots(tree.root_node, path, line_count, diagnostics)
        return ExtractionResult(
            nodes=tuple(nodes),
            observations=assign_ordinals(observations),
            diagnostics=tuple(diagnostics),
        )

    def _collect_imports(self, root, path, line_count, file_key, observations) -> None:
        source = root.text

        def walk(node):
            if node.type in ("import_statement", "export_statement"):
                source_node = node.child_by_field_name("source")
                if source_node is not None:
                    literal = self._node_text(source_node, source).strip("'\"`")
                    ev, _ = build_evidence(
                        path, node.start_point[0] + 1, node.end_point[0] + 1,
                        line_count, producer=self.producer,
                    )
                    if ev is not None:
                        observations.append(
                            ExtractedObservation(
                                observed_kind="import", subject_kind="file",
                                subject_key=file_key, referent_text=literal,
                                ordinal=_UNASSIGNED_ORDINAL, evidence=ev,
                            )
                        )
            for child in node.named_children:
                walk(child)

        walk(root)

    def _collect_routes(self, root, path, line_count, file_key, observations) -> None:
        """Emit a ``route`` observation per confirmed react-router path literal.

        Only two contexts count: a ``path`` key inside an argument to a router
        factory (``createBrowserRouter`` and friends), and a ``path`` attribute
        on a ``<Route>`` element. A bare ``{path: ...}`` object or a ``path``
        prop on any other component is not a route, and inventing one would be a
        fabricated fact (RFC §7.2).
        """

        source = root.text
        seen: set[int] = set()

        def emit(node, literal):
            if node.id in seen:
                return
            seen.add(node.id)
            ev, _ = build_evidence(
                path, node.start_point[0] + 1, node.end_point[0] + 1,
                line_count, producer=self.producer,
            )
            if ev is not None:
                observations.append(
                    ExtractedObservation(
                        observed_kind="route", subject_kind="file",
                        subject_key=file_key, referent_text=literal,
                        ordinal=_UNASSIGNED_ORDINAL, evidence=ev,
                    )
                )

        def pair_value(pair, name):
            key = pair.child_by_field_name("key")
            if key is None or self._node_text(key, source).strip("'\"") != name:
                return None
            return pair.child_by_field_name("value")

        def collect_route_entry(node):
            """Read direct route fields and follow only its ``children`` table.

            A route entry is an object in the router's route-table array. Its
            ``handle``, ``element``, and arbitrary metadata may contain objects
            with their own ``path`` keys, but those are application data rather
            than routes. ``children`` is the one RouteObject field that contains
            another route table.
            """

            if node.type != "object":
                return
            for pair in node.named_children:
                if pair.type != "pair":
                    continue
                path_value = pair_value(pair, "path")
                if path_value is not None and path_value.type == "string":
                    emit(pair, self._node_text(path_value, source).strip("'\"`"))
                children_value = pair_value(pair, "children")
                if children_value is not None:
                    collect_route_table(children_value)

        def collect_route_table(node):
            # A factory's first argument and a route entry's `children` must be
            # arrays of actual route objects. Do not recursively inspect their
            # contents: unrelated nested objects are not route entries.
            if node.type == "array":
                for entry in node.named_children:
                    collect_route_entry(entry)

        def walk(node):
            if node.type == "call_expression":
                fn = node.child_by_field_name("function")
                arguments = node.child_by_field_name("arguments")
                if (fn is not None and arguments is not None
                        and self._node_text(fn, source) in _ROUTER_FACTORIES):
                    # createBrowserRouter(routes, opts?) — only the first argument
                    # is the route table. The options object also accepts a `path`
                    # (e.g. basename config), which is not a route.
                    route_table = arguments.named_children[0] if arguments.named_children else None
                    if route_table is not None:
                        collect_route_table(route_table)
            elif node.type in ("jsx_self_closing_element", "jsx_opening_element"):
                name_node = node.child_by_field_name("name")
                if (name_node is not None
                        and self._node_text(name_node, source) in _ROUTE_ELEMENTS):
                    for child in node.named_children:
                        if child.type != "jsx_attribute":
                            continue
                        parts = child.named_children
                        if (len(parts) > 1
                                and self._node_text(parts[0], source) == "path"):
                            emit(child, self._node_text(parts[1], source).strip("'\"{}`"))
            for child in node.named_children:
                walk(child)

        walk(root)

    def _collect_blind_spots(self, root, path, line_count, diagnostics) -> None:
        source = root.text
        normalized = canonical.normalize_repo_path(path)
        file_subject = canonical.normalize_stable_key("file", f"file:{normalized}")

        def flag(node, message):
            diagnostics.append(
                ExtractedDiagnostic(
                    code=RI_EXT_UNSUPPORTED, category="unsupported construct",
                    severity="info", message=message, path=normalized,
                    span=(node.start_point[0] + 1, node.end_point[0] + 1),
                    subject=file_subject,
                )
            )

        def walk(node):
            if node.type in ("internal_module", "module") and node.child_by_field_name("name") is not None:
                flag(node, "namespace/module declaration is unsupported")
            elif node.type == "decorator":
                # TypeScript decorators are declared unsupported: their semantics
                # (and any metadata they attach) are not modelled here. The
                # message names the construct only — quoting the decorator source
                # would embed repository content, and its arguments can hold
                # secrets (RFC §13). The span says where to look.
                flag(node, "TypeScript decorator is unsupported")
            elif node.type == "call_expression":
                fn = node.child_by_field_name("function")
                if fn is not None:
                    text = self._node_text(fn, source)
                    if fn.type == "import":
                        flag(node, "dynamic import() is unsupported")
                    elif text == "require":
                        flag(node, "CommonJS require() is unsupported")
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
                    subject_key=key, referent_text=None,
                    ordinal=_UNASSIGNED_ORDINAL, evidence=ev,
                )
            )
            if duplicate:
                diagnostics.append(
                    ExtractedDiagnostic(
                        code=RI_KEY_DUP_SYMBOL, category="duplicate symbol",
                        severity="info",
                        # The key lives in `subject`, the field meant for it;
                        # repeating it here would put source-derived text in
                        # `message`, which RFC §13 reserves from content.
                        message="duplicate symbol name resolved with a discriminator",
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
