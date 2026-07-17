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
        self._collect_implements(tree.root_node, path, line_count, nodes, observations)
        self._collect_imports(tree.root_node, path, line_count, file_key, observations)
        self._collect_routes(tree.root_node, path, line_count, file_key, nodes, observations)
        self._collect_calls(tree.root_node, path, line_count, file_key, observations)
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
                        if node.type == "import_statement":
                            self._collect_import_bindings(
                                node, literal, path, line_count, file_key, source, observations
                            )
            for child in node.named_children:
                walk(child)

        walk(root)

    def _collect_implements(self, root, path, line_count, nodes, observations) -> None:
        """Emit direct TypeScript ``class ... implements ...`` references.

        Only the syntax-level `implements` clause is recorded. Resolving an
        imported interface name is left to the stored-fact resolver, and
        ``extends`` remains outside the registered v1 predicate set.
        """

        source = root.text
        symbols = {node.stable_key: node for node in nodes if node.node_kind == "symbol"}

        def walk(node):
            if node.type == "class_declaration":
                name = node.child_by_field_name("name")
                if name is not None:
                    class_key = canonical.normalize_stable_key(
                        "symbol", symbol_stable_key(path, [], self._node_text(name, source))
                    )
                    if class_key in symbols:
                        heritage = next(
                            (child for child in node.named_children if child.type == "class_heritage"),
                            None,
                        )
                        if heritage is not None:
                            for clause in heritage.named_children:
                                if clause.type != "implements_clause":
                                    continue
                                for target in clause.named_children:
                                    evidence, _ = build_evidence(
                                        path,
                                        target.start_point[0] + 1,
                                        target.end_point[0] + 1,
                                        line_count,
                                        producer=self.producer,
                                    )
                                    if evidence is not None:
                                        observations.append(
                                            ExtractedObservation(
                                                observed_kind="implements",
                                                subject_kind="symbol",
                                                subject_key=class_key,
                                                referent_text=self._node_text(target, source),
                                                ordinal=_UNASSIGNED_ORDINAL,
                                                evidence=evidence,
                                            )
                                        )
            for child in node.named_children:
                walk(child)

        walk(root)

    def _collect_import_bindings(
        self, statement, specifier, path, line_count, file_key, source, observations
    ) -> None:
        """Record direct import aliases as resolver inputs without resolving them."""

        clause = next((child for child in statement.named_children if child.type == "import_clause"), None)
        if clause is None:
            return

        def emit(imported, local, node):
            evidence, _ = build_evidence(
                path, node.start_point[0] + 1, node.end_point[0] + 1,
                line_count, producer=self.producer,
            )
            if evidence is not None:
                observations.append(
                    ExtractedObservation(
                        observed_kind="import_binding",
                        subject_kind="file",
                        subject_key=file_key,
                        # This is an exact, delimiter-safe representation of the
                        # source binding.  The resolver consumes it as stored
                        # extractor output; it never re-parses the source file.
                        referent_text=f"{specifier}|{imported}|{local}",
                        ordinal=_UNASSIGNED_ORDINAL,
                        evidence=evidence,
                    )
                )

        for child in clause.named_children:
            if child.type == "identifier":
                emit("default", self._node_text(child, source), child)
            elif child.type == "named_imports":
                for binding in child.named_children:
                    if binding.type != "import_specifier":
                        continue
                    name = binding.child_by_field_name("name")
                    alias = binding.child_by_field_name("alias")
                    if name is not None:
                        emit(
                            self._node_text(name, source),
                            self._node_text(alias, source) if alias is not None else self._node_text(name, source),
                            binding,
                        )

    def _collect_routes(self, root, path, line_count, file_key, nodes, observations) -> None:
        """Emit a ``route`` observation per confirmed react-router path literal.

        Only two contexts count: a ``path`` key inside an argument to a router
        factory (``createBrowserRouter`` and friends), and a ``path`` attribute
        on a ``<Route>`` element. A bare ``{path: ...}`` object or a ``path``
        prop on any other component is not a route, and inventing one would be a
        fabricated fact (RFC §7.2).
        """

        source = root.text
        seen: set[int] = set()
        route_ordinal = 0

        def emit(node, literal, handler_referent=None, handler_node=None):
            nonlocal route_ordinal
            if node.id in seen:
                return
            seen.add(node.id)
            ev, _ = build_evidence(
                path, node.start_point[0] + 1, node.end_point[0] + 1,
                line_count, producer=self.producer,
            )
            if ev is not None:
                route_ordinal += 1
                route_key = canonical.normalize_stable_key(
                    "symbol",
                    symbol_stable_key(path, [], f"(anonymous:route#{route_ordinal})"),
                )
                nodes.append(
                    ExtractedNode(
                        node_kind="symbol",
                        stable_key=route_key,
                        name="route",
                        language="typescript",
                        evidence=(ev,),
                        properties={"route_path": literal},
                    )
                )
                observations.append(
                    ExtractedObservation(
                        observed_kind="route", subject_kind="symbol",
                        subject_key=route_key, referent_text=literal,
                        ordinal=_UNASSIGNED_ORDINAL, evidence=ev,
                    )
                )
                if handler_referent:
                    handler_ev, _ = build_evidence(
                        path,
                        handler_node.start_point[0] + 1 if handler_node is not None else node.start_point[0] + 1,
                        handler_node.end_point[0] + 1 if handler_node is not None else node.end_point[0] + 1,
                        line_count,
                        producer=self.producer,
                    )
                    if handler_ev is not None:
                        observations.append(
                            ExtractedObservation(
                                observed_kind="route_handler",
                                subject_kind="symbol",
                                subject_key=route_key,
                                referent_text=handler_referent,
                                ordinal=_UNASSIGNED_ORDINAL,
                                evidence=handler_ev,
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
            path_pair = None
            path_value = None
            handler_referent = None
            handler_node = None
            child_tables = []
            for pair in node.named_children:
                if pair.type != "pair":
                    continue
                candidate_path = pair_value(pair, "path")
                if candidate_path is not None and candidate_path.type == "string":
                    path_pair, path_value = pair, candidate_path
                for handler_name in ("Component", "component"):
                    handler_value = pair_value(pair, handler_name)
                    if handler_value is not None and handler_value.type == "identifier":
                        handler_referent, handler_node = self._node_text(handler_value, source), handler_value
                element_value = pair_value(pair, "element")
                if element_value is not None:
                    jsx_handler = self._jsx_handler(element_value, source)
                    if jsx_handler is not None:
                        handler_referent, handler_node = jsx_handler
                children_value = pair_value(pair, "children")
                if children_value is not None:
                    child_tables.append(children_value)
            if path_pair is not None and path_value is not None:
                emit(
                    path_pair,
                    self._node_text(path_value, source).strip("'\"`"),
                    handler_referent,
                    handler_node,
                )
            for child_table in child_tables:
                collect_route_table(child_table)

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
                    path_attribute = None
                    handler_referent = None
                    handler_node = None
                    for child in node.named_children:
                        if child.type != "jsx_attribute":
                            continue
                        parts = child.named_children
                        if (len(parts) > 1
                                and self._node_text(parts[0], source) == "path"):
                            path_attribute = child
                            path_literal = self._node_text(parts[1], source).strip("'\"{}`")
                        elif (len(parts) > 1
                              and self._node_text(parts[0], source) == "element"):
                            jsx_handler = self._jsx_handler(parts[1], source)
                            if jsx_handler is not None:
                                handler_referent, handler_node = jsx_handler
                    if path_attribute is not None:
                        emit(path_attribute, path_literal, handler_referent, handler_node)
            for child in node.named_children:
                walk(child)

        walk(root)

    def _jsx_handler(self, node, source: bytes):
        """Return a direct JSX component reference, never a computed expression."""

        if node.type == "jsx_expression" and node.named_children:
            node = node.named_children[0]
        if node.type not in ("jsx_element", "jsx_self_closing_element"):
            return None
        name = node.child_by_field_name("name")
        if name is None:
            return None
        text = self._node_text(name, source)
        return (text, name) if text and text[0].isupper() else None

    def _collect_calls(self, root, path, line_count, file_key, observations) -> None:
        """Record direct identifier calls; target selection is resolver work."""

        source = root.text

        def walk(node):
            if node.type == "call_expression":
                function = node.child_by_field_name("function")
                if function is not None and function.type == "identifier":
                    function_name = self._node_text(function, source)
                    # CommonJS require() remains an explicitly unsupported
                    # construct, so its diagnostic is the only emitted fact.
                    if function_name != "require":
                        evidence, _ = build_evidence(
                            path, node.start_point[0] + 1, node.end_point[0] + 1,
                            line_count, producer=self.producer,
                        )
                        if evidence is not None:
                            observations.append(
                                ExtractedObservation(
                                    observed_kind="call",
                                    subject_kind="file",
                                    subject_key=file_key,
                                    referent_text=function_name,
                                    ordinal=_UNASSIGNED_ORDINAL,
                                    evidence=evidence,
                                )
                            )
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
