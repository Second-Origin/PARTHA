from __future__ import annotations

import ast

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
_REFLECTION_CALLS = {"getattr", "setattr", "delattr"}

# Collectors emit this; assign_ordinals sets the RFC §6.4 value on the way out.
# It is deliberately invalid (ordinals are one-based) so a result that skipped
# assignment fails loudly rather than persisting a wrong identity.
_UNASSIGNED_ORDINAL = 0

_BINDING_LOCAL = "local"
_BINDING_IMPORTED = "imported"
_BINDING_IMPORTLIB_MODULE = "importlib-module"
_BINDING_IMPORTLIB_FUNCTION = "importlib-import-module"


class _ScopeDeclarations(ast.NodeVisitor):
    """Find bindings that Python makes local for an entire function scope."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def visit_Name(self, node) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Import(self, node) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.names.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node) -> None:
        self.names.add(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, node) -> None:
        # A lambda has its own lexical scope.
        return

    def visit_Global(self, node) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node) -> None:
        self.nonlocal_names.update(node.names)


class _BindingScope:
    """The subset of Python name resolution needed by blind-spot diagnostics."""

    def __init__(
        self,
        parent: _BindingScope | None = None,
        *,
        kind: str = "module",
        bindings: dict[str, str] | None = None,
        global_names: set[str] | None = None,
        nonlocal_names: set[str] | None = None,
    ) -> None:
        self.parent = parent
        self.kind = kind
        self.bindings = bindings or {}
        self.global_names = global_names or set()
        self.nonlocal_names = nonlocal_names or set()

    def _module_scope(self) -> _BindingScope:
        scope = self
        while scope.parent is not None:
            scope = scope.parent
        return scope

    def _nonlocal_parent(self) -> _BindingScope | None:
        scope = self.parent
        while scope is not None and scope.kind == "class":
            scope = scope.parent
        return scope

    def resolve(self, name: str) -> str | None:
        if name in self.global_names:
            return self._module_scope().bindings.get(name)
        if name in self.nonlocal_names:
            parent = self._nonlocal_parent()
            return parent.resolve(name) if parent is not None else None
        if name in self.bindings:
            return self.bindings[name]
        return self.parent.resolve(name) if self.parent is not None else None

    def bind(self, name: str, binding: str) -> None:
        if name in self.global_names:
            self._module_scope().bindings[name] = binding
        elif name in self.nonlocal_names:
            parent = self._nonlocal_parent()
            if parent is not None:
                parent.bind(name, binding)
        else:
            self.bindings[name] = binding


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

    def _attribute_root(self, node):
        """Resolve ``a.b.c`` to its root ``Name``, or None if not name-rooted."""

        while isinstance(node, ast.Attribute):
            node = node.value
        return node if isinstance(node, ast.Name) else None

    def _function_scope(self, node, parent: _BindingScope) -> _BindingScope:
        declarations = _ScopeDeclarations()
        body = node.body if isinstance(node.body, list) else []
        for statement in body:
            declarations.visit(statement)

        arguments = node.args
        parameters = [
            *(argument.arg for argument in arguments.posonlyargs),
            *(argument.arg for argument in arguments.args),
            *(argument.arg for argument in arguments.kwonlyargs),
        ]
        if arguments.vararg is not None:
            parameters.append(arguments.vararg.arg)
        if arguments.kwarg is not None:
            parameters.append(arguments.kwarg.arg)

        local_names = (declarations.names | set(parameters)) - declarations.global_names - declarations.nonlocal_names
        return _BindingScope(
            parent,
            kind="function",
            bindings={name: _BINDING_LOCAL for name in local_names},
            global_names=declarations.global_names,
            nonlocal_names=declarations.nonlocal_names,
        )

    @staticmethod
    def _function_parent(scope: _BindingScope) -> _BindingScope:
        # A method's unqualified names do not resolve through its class body.
        while scope.kind == "class" and scope.parent is not None:
            scope = scope.parent
        return scope

    @staticmethod
    def _assignment_attributes(target):
        """Yield attributes from assignment targets, including unpacking."""

        if isinstance(target, ast.Attribute):
            yield target
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                yield from PythonExtractor._assignment_attributes(element)
        elif isinstance(target, ast.Starred):
            yield from PythonExtractor._assignment_attributes(target.value)

    @staticmethod
    def _target_names(target):
        if isinstance(target, ast.Name):
            yield target.id
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                yield from PythonExtractor._target_names(element)
        elif isinstance(target, ast.Starred):
            yield from PythonExtractor._target_names(target.value)

    def _collect_blind_spots(self, tree, path, line_count, diagnostics) -> None:
        normalized = canonical.normalize_repo_path(path)

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

        def bind_import(node, scope: _BindingScope) -> None:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".", 1)[0]
                    is_importlib_module = alias.name == "importlib" or (
                        alias.asname is None and alias.name.startswith("importlib.")
                    )
                    scope.bind(
                        name,
                        _BINDING_IMPORTLIB_MODULE if is_importlib_module else _BINDING_IMPORTED,
                    )
            else:
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    is_import_module = node.module == "importlib" and alias.name == "import_module"
                    scope.bind(
                        name,
                        _BINDING_IMPORTLIB_FUNCTION if is_import_module else _BINDING_IMPORTED,
                    )

        def bind_target_names(target, scope: _BindingScope) -> None:
            for name in self._target_names(target):
                scope.bind(name, _BINDING_LOCAL)

        def is_imported_name(name: str, scope: _BindingScope) -> bool:
            return scope.resolve(name) in {
                _BINDING_IMPORTED,
                _BINDING_IMPORTLIB_MODULE,
                _BINDING_IMPORTLIB_FUNCTION,
            }

        def flag_monkeypatch(node, targets, scope: _BindingScope) -> None:
            for target in targets:
                for attribute in self._assignment_attributes(target):
                    root = self._attribute_root(attribute)
                    if root is not None and is_imported_name(root.id, scope):
                        flag(node, "monkey-patching an imported name is unsupported")
                        return

        def is_dynamic_import_call(func, scope: _BindingScope) -> str | None:
            if isinstance(func, ast.Name):
                if func.id == "__import__":
                    # It is built in only while this scope has not rebound it.
                    return func.id if scope.resolve(func.id) is None else None
                if scope.resolve(func.id) == _BINDING_IMPORTLIB_FUNCTION:
                    return "import_module"
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and isinstance(func.value, ast.Name)
                and scope.resolve(func.value.id) == _BINDING_IMPORTLIB_MODULE
            ):
                return "import_module"
            return None

        def scan_function_signature(node, scope: _BindingScope) -> None:
            for decorator in node.decorator_list:
                scan(decorator, scope)
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    scan(default, scope)
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ):
                if argument.annotation is not None:
                    scan(argument.annotation, scope)
            if node.args.vararg is not None and node.args.vararg.annotation is not None:
                scan(node.args.vararg.annotation, scope)
            if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
                scan(node.args.kwarg.annotation, scope)
            if node.returns is not None:
                scan(node.returns, scope)

        def scan(node, scope: _BindingScope) -> None:
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "*" for alias in node.names):
                    flag(node, "star-import is unsupported")
                bind_import(node, scope)
            elif isinstance(node, ast.Import):
                bind_import(node, scope)
            elif isinstance(node, ast.ClassDef):
                if any(
                    keyword.arg == "metaclass" for keyword in node.keywords
                ):
                    # The class itself is still extracted; what a metaclass does to it
                    # at runtime is not modelled, so say so rather than imply we know.
                    flag(node, "metaclass is unsupported")
                for decorator in node.decorator_list:
                    scan(decorator, scope)
                for base in node.bases:
                    scan(base, scope)
                for keyword in node.keywords:
                    scan(keyword.value, scope)
                scope.bind(node.name, _BINDING_LOCAL)
                class_scope = _BindingScope(scope, kind="class")
                for statement in node.body:
                    scan(statement, class_scope)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scan_function_signature(node, scope)
                scope.bind(node.name, _BINDING_LOCAL)
                function_scope = self._function_scope(node, self._function_parent(scope))
                for statement in node.body:
                    scan(statement, function_scope)
            elif isinstance(node, ast.Lambda):
                for default in (*node.args.defaults, *node.args.kw_defaults):
                    if default is not None:
                        scan(default, scope)
                lambda_scope = self._function_scope(node, self._function_parent(scope))
                scan(node.body, lambda_scope)
            elif isinstance(node, ast.Assign):
                scan(node.value, scope)
                flag_monkeypatch(node, node.targets, scope)
                for target in node.targets:
                    bind_target_names(target, scope)
            elif isinstance(node, ast.AugAssign):
                scan(node.value, scope)
                flag_monkeypatch(node, [node.target], scope)
                bind_target_names(node.target, scope)
            elif isinstance(node, ast.AnnAssign):
                if node.annotation is not None:
                    scan(node.annotation, scope)
                if node.value is not None:
                    scan(node.value, scope)
                flag_monkeypatch(node, [node.target], scope)
                bind_target_names(node.target, scope)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                scan(node.iter, scope)
                flag_monkeypatch(node, [node.target], scope)
                bind_target_names(node.target, scope)
                for statement in node.body:
                    scan(statement, scope)
                for statement in node.orelse:
                    scan(statement, scope)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    scan(item.context_expr, scope)
                    if item.optional_vars is not None:
                        flag_monkeypatch(node, [item.optional_vars], scope)
                        bind_target_names(item.optional_vars, scope)
                for statement in node.body:
                    scan(statement, scope)
            elif isinstance(node, ast.ExceptHandler):
                if node.type is not None:
                    scan(node.type, scope)
                if node.name is not None:
                    scope.bind(node.name, _BINDING_LOCAL)
                for statement in node.body:
                    scan(statement, scope)
            elif isinstance(node, ast.NamedExpr):
                scan(node.value, scope)
                bind_target_names(node.target, scope)
            elif isinstance(node, ast.Call):
                func = node.func
                # These names come from this module's own closed vocabulary, not
                # from arbitrary source text, so naming them leaks nothing.
                if isinstance(func, ast.Name) and func.id in _REFLECTION_CALLS:
                    flag(node, f"reflection via {func.id}() is unsupported")
                else:
                    dynamic_import = is_dynamic_import_call(func, scope)
                    if dynamic_import is not None:
                        flag(node, f"dynamic import via {dynamic_import}() is unsupported")
                for child in ast.iter_child_nodes(node):
                    scan(child, scope)
            else:
                for child in ast.iter_child_nodes(node):
                    scan(child, scope)

        module_scope = _BindingScope()
        for statement in tree.body:
            scan(statement, module_scope)

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
