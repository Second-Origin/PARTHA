"""Deterministic relationship resolution over a building RI snapshot (#91).

Resolvers read stored nodes, observations, and evidence only.  They never read
the repository working tree: the extractor output is the complete input
surface.  A relationship is emitted only when the documented candidate set has
exactly one member; zero and multiple candidates become visible diagnostics.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
import posixpath
import re

from sqlalchemy import select

from app.intelligence.snapshot_store import Evidence, SnapshotStateError, SnapshotStore
from app.models.snapshot import RiEvidence, RiNode, RiObservation, RiSnapshot


RI_RES_UNRESOLVED = "RI-RES-UNRESOLVED"
RI_RES_AMBIGUOUS = "RI-RES-AMBIGUOUS"


@dataclass(frozen=True)
class ResolutionResult:
    """The materialized facts from one deterministic resolver pass."""

    edges_added: int
    diagnostics_added: int


@dataclass(frozen=True)
class _ObservedInput:
    observation: RiObservation
    evidence: RiEvidence


class RelationshipResolver:
    """Resolve the #91 relationship kinds from snapshot-persisted observations.

    Supported stored observation kinds are deliberately small and explicit:

    ``definition``
        A symbol definition.  It resolves ``contains`` and ``defines`` from its
        lexical parent (or its file for top-level symbols).
    ``import``
        A TypeScript/Python module specifier.  It resolves a local file or an
        already-observed dependency node.
    ``call`` / ``call_shadowed`` / ``implements``
        A direct reference.  It resolves only through proven evidence — a full
        stable key, a same-file top-level definition, or an explicit import
        binding — never a repository-wide same-name guess. ``call_shadowed``
        marks a call-site name that lexical extraction proved local, forcing the
        paired call to remain unresolved instead of borrowing a global/imported
        symbol. Multiple binding targets stay ambiguous; missing evidence stays
        unresolved.
    ``route`` + ``route_handler``
        A route symbol and its extractor-recorded handler reference.  Both are
        needed, so a literal path alone is never treated as a handler claim.
    ``dependency``
        A manifest-backed dependency declaration whose subject is a dependency
        node.  It resolves ``repo:root -> dependency``.
    ``injects``
        A ``Depends(name)`` argument (#95).  Resolved exactly like a ``call``:
        through proven evidence only, attributed to whichever symbol's span
        contains it.  Produces an ``injects`` edge from the containing
        function to the referenced dependency callable.

    New extractors can add observation kinds without making this class guess:
    unsupported kinds are simply not relationship inputs.
    """

    name = "relationship-resolver"
    version = "1.0.0"

    def __init__(self, store: SnapshotStore) -> None:
        self.store = store
        self._snapshot: RiSnapshot | None = None

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def resolve(
        self,
        snapshot: RiSnapshot,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> ResolutionResult:
        """Add every resolvable #91 edge to one *building* snapshot.

        Existing matching edges are consolidated by :class:`SnapshotStore`; the
        result count is consequently a count of attempted resolved facts rather
        than a database-row count.  Inputs are sorted by observation id so a
        different insertion order cannot change facts or diagnostics.
        """

        self._check_cancelled(check_cancelled)
        if snapshot.state != "building":
            raise SnapshotStateError("relationship resolution requires a building snapshot")
        if self.producer not in set(snapshot.producer_version_set):
            raise ValueError(f"snapshot producer_version_set is missing {self.producer!r}")
        self._snapshot = snapshot

        nodes: list[RiNode] = []
        for node in self.store.db.scalars(select(RiNode).where(RiNode.snapshot_id == snapshot.snapshot_id)).yield_per(
            500
        ):
            self._check_cancelled(check_cancelled)
            nodes.append(node)
        nodes_by_key = {node.stable_key: node for node in nodes}
        self._check_cancelled(check_cancelled)
        observations: list[RiObservation] = []
        for observation in self.store.db.scalars(
            select(RiObservation)
            .where(RiObservation.snapshot_id == snapshot.snapshot_id)
            .order_by(RiObservation.observation_id)
        ).yield_per(500):
            self._check_cancelled(check_cancelled)
            observations.append(observation)
        evidence_by_observation: dict[int, list[RiEvidence]] = defaultdict(list)
        evidence_by_node: dict[int, list[RiEvidence]] = defaultdict(list)
        for evidence in self.store.db.scalars(
            select(RiEvidence).where(RiEvidence.snapshot_id == snapshot.snapshot_id)
        ).yield_per(500):
            self._check_cancelled(check_cancelled)
            if evidence.observation_ref is not None:
                evidence_by_observation[evidence.observation_ref].append(evidence)
            if evidence.node_ref is not None:
                evidence_by_node[evidence.node_ref].append(evidence)

        inputs: list[_ObservedInput] = []
        for observation in observations:
            self._check_cancelled(check_cancelled)
            evidence = evidence_by_observation.get(observation.id)
            if evidence:
                inputs.append(
                    _ObservedInput(
                        observation,
                        sorted(evidence, key=self._evidence_key)[0],
                    )
                )
        inputs_by_kind: dict[str, list[_ObservedInput]] = defaultdict(list)
        for input_ in inputs:
            self._check_cancelled(check_cancelled)
            inputs_by_kind[input_.observation.observed_kind].append(input_)
        bindings_by_file: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for input_ in inputs_by_kind["import_binding"]:
            self._check_cancelled(check_cancelled)
            source = self._source_file(input_, nodes_by_key)
            parsed = self._parse_import_binding(input_.observation.referent_text)
            if source is not None and parsed is not None:
                bindings_by_file[source.stable_key].append(parsed)
        shadowed_calls: set[tuple[str, str | None, str, int, int, int]] = set()
        for input_ in inputs_by_kind["call_shadowed"]:
            self._check_cancelled(check_cancelled)
            shadowed_calls.add(self._reference_input_key(input_))

        edges_added = 0
        diagnostics_added = 0

        for input_ in inputs_by_kind["definition"]:
            self._check_cancelled(check_cancelled)
            added, diagnosed = self._resolve_definition(input_, nodes_by_key)
            edges_added += added
            diagnostics_added += diagnosed

        for input_ in inputs_by_kind["import"]:
            self._check_cancelled(check_cancelled)
            added, diagnosed = self._resolve_import(input_, nodes_by_key, bindings_by_file)
            edges_added += added
            diagnostics_added += diagnosed

        for input_ in inputs_by_kind["call"]:
            self._check_cancelled(check_cancelled)
            if self._reference_input_key(input_) in shadowed_calls:
                added, diagnosed = self._unresolved(input_, "calls target is shadowed by a local binding")
            else:
                added, diagnosed = self._resolve_reference(
                    input_, nodes_by_key, evidence_by_node, bindings_by_file, predicate="calls"
                )
            edges_added += added
            diagnostics_added += diagnosed

        for input_ in inputs_by_kind["implements"]:
            self._check_cancelled(check_cancelled)
            added, diagnosed = self._resolve_reference(
                input_, nodes_by_key, evidence_by_node, bindings_by_file, predicate="implements"
            )
            edges_added += added
            diagnostics_added += diagnosed

        for input_ in inputs_by_kind["dependency"]:
            self._check_cancelled(check_cancelled)
            added, diagnosed = self._resolve_dependency(input_, nodes_by_key)
            edges_added += added
            diagnostics_added += diagnosed

        for input_ in inputs_by_kind["injects"]:
            self._check_cancelled(check_cancelled)
            added, diagnosed = self._resolve_reference(
                input_, nodes_by_key, evidence_by_node, bindings_by_file, predicate="injects"
            )
            edges_added += added
            diagnostics_added += diagnosed

        route_handlers: dict[str, list[_ObservedInput]] = defaultdict(list)
        for input_ in inputs_by_kind["route_handler"]:
            self._check_cancelled(check_cancelled)
            route_handlers[input_.observation.subject_key].append(input_)
        for input_ in inputs_by_kind["route"]:
            self._check_cancelled(check_cancelled)
            added, diagnosed = self._resolve_route(
                input_,
                route_handlers.get(input_.observation.subject_key, ()),
                nodes_by_key,
                bindings_by_file,
            )
            edges_added += added
            diagnostics_added += diagnosed

        return ResolutionResult(edges_added=edges_added, diagnostics_added=diagnostics_added)

    @staticmethod
    def _check_cancelled(check_cancelled: Callable[[], None] | None) -> None:
        if check_cancelled is not None:
            check_cancelled()

    def _resolve_definition(self, input_: _ObservedInput, nodes_by_key: dict[str, RiNode]) -> tuple[int, int]:
        observation = input_.observation
        symbol = nodes_by_key.get(observation.subject_key)
        if symbol is None or symbol.node_kind != "symbol" or "::" not in symbol.stable_key:
            return self._unresolved(input_, "definition has no resolvable symbol parent")
        path, qualified = symbol.stable_key.split("::", 1)
        if "." in qualified:
            parent_key = f"{path}::{qualified.rsplit('.', 1)[0]}"
        else:
            parent_key = f"file:{path}"
        parent = nodes_by_key.get(parent_key)
        if parent is None:
            return self._unresolved(input_, "definition parent is absent from the snapshot")
        self._add_edge(input_, parent, "contains", symbol)
        self._add_edge(input_, parent, "defines", symbol)
        return 2, 0

    def _resolve_import(
        self,
        input_: _ObservedInput,
        nodes_by_key: dict[str, RiNode],
        bindings_by_file: dict[str, list[tuple[str, str, str]]],
    ) -> tuple[int, int]:
        subject = self._source_file(input_, nodes_by_key)
        if subject is None:
            return self._unresolved(input_, "import source file is absent from the snapshot")
        specifier = input_.observation.referent_text
        if not specifier:
            return self._unresolved(input_, "import has no module specifier")
        candidates = self._import_candidates(
            specifier,
            input_.evidence.path,
            subject,
            nodes_by_key,
            bindings_by_file.get(subject.stable_key, ()),
        )
        return self._resolve_candidates(input_, subject, "imports", candidates)

    def _resolve_reference(
        self,
        input_: _ObservedInput,
        nodes_by_key: dict[str, RiNode],
        evidence_by_node: dict[int, list[RiEvidence]],
        bindings_by_file: dict[str, list[tuple[str, str, str]]],
        *,
        predicate: str,
    ) -> tuple[int, int]:
        observed_subject = nodes_by_key.get(input_.observation.subject_key)
        subject = observed_subject
        if subject is None or subject.node_kind != "symbol":
            subject = self._containing_symbol(input_, nodes_by_key, evidence_by_node)
            if (
                subject is None
                and observed_subject is not None
                and observed_subject.node_kind
                in {
                    "file",
                    "module",
                }
            ):
                subject = observed_subject
        if subject is None:
            return self._unresolved(input_, f"{predicate} source symbol is absent from the snapshot")
        referent = input_.observation.referent_text
        if not referent:
            return self._unresolved(input_, f"{predicate} has no reference text")
        return self._resolve_candidates(
            input_,
            subject,
            predicate,
            self._reference_candidates(
                referent,
                input_.evidence.path,
                nodes_by_key,
                bindings_by_file.get(f"file:{input_.evidence.path}", ()),
            ),
        )

    def _resolve_dependency(self, input_: _ObservedInput, nodes_by_key: dict[str, RiNode]) -> tuple[int, int]:
        dependency = nodes_by_key.get(input_.observation.subject_key)
        repository = nodes_by_key.get("repo:root")
        if dependency is None or dependency.node_kind != "dependency" or repository is None:
            return self._unresolved(input_, "dependency declaration is incomplete")
        self._add_edge(input_, repository, "depends_on", dependency)
        return 1, 0

    def _resolve_route(
        self,
        route: _ObservedInput,
        handlers: list[_ObservedInput] | tuple[_ObservedInput, ...],
        nodes_by_key: dict[str, RiNode],
        bindings_by_file: dict[str, list[tuple[str, str, str]]],
    ) -> tuple[int, int]:
        route_node = nodes_by_key.get(route.observation.subject_key)
        if route_node is None or route_node.node_kind != "symbol":
            return self._unresolved(route, "route declaration is absent from the snapshot")
        if len(handlers) != 1:
            if not handlers:
                return self._unresolved(route, "route has no observed handler reference")
            return self._ambiguous(route, "route has more than one handler reference", ())
        handler = handlers[0]
        referent = handler.observation.referent_text
        if not referent:
            return self._unresolved(handler, "route handler has no reference text")
        return self._resolve_candidates(
            handler,
            route_node,
            "routes_to",
            self._reference_candidates(
                referent,
                handler.evidence.path,
                nodes_by_key,
                bindings_by_file.get(f"file:{handler.evidence.path}", ()),
            ),
        )

    def _resolve_candidates(
        self,
        input_: _ObservedInput,
        subject: RiNode,
        predicate: str,
        candidates: list[RiNode],
    ) -> tuple[int, int]:
        unique = {candidate.stable_key: candidate for candidate in candidates}
        ordered = [unique[key] for key in sorted(unique)]
        if not ordered:
            return self._unresolved(input_, f"{predicate} has no resolvable target")
        if len(ordered) > 1:
            return self._ambiguous(input_, f"{predicate} has more than one candidate target", tuple(unique))
        self._add_edge(input_, subject, predicate, ordered[0])
        return 1, 0

    def _import_candidates(
        self,
        specifier: str,
        source_path: str,
        source: RiNode,
        nodes_by_key: dict[str, RiNode],
        bindings: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...] = (),
    ) -> list[RiNode]:
        file_candidates: set[str] = set()
        if specifier.startswith("."):
            file_candidates.update(self._relative_file_candidates(specifier, source_path))
        elif source_path.endswith(".py") and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", specifier):
            file_candidates.update(self._python_absolute_file_candidates(specifier))
            # ``from a.b import c`` is stored as import referent ``a.b.c`` whose
            # module is ``a.b`` — the imported name may be a submodule (``a/b/c.py``)
            # or a member of ``a/b.py``.  The stored binding preserves that split,
            # so the module file resolves without reparsing the source.
            for binding_specifier, imported, _local in bindings:
                if binding_specifier and f"{binding_specifier}.{imported}" == specifier:
                    file_candidates.update(self._python_absolute_file_candidates(binding_specifier))
        files = [
            node
            for key, node in nodes_by_key.items()
            if key in {f"file:{path}" for path in file_candidates} and node.node_kind == "file"
        ]
        if files:
            return files

        package = self._package_root(specifier, source_path)
        normalized_python = re.sub(r"[-_.]+", "-", package).lower()
        return [
            node
            for node in nodes_by_key.values()
            if node.node_kind == "dependency"
            and (node.stable_key == f"dep:npm:{package}" or node.stable_key == f"dep:pypi:{normalized_python}")
        ]

    @staticmethod
    def _relative_file_candidates(specifier: str, source_path: str) -> set[str]:
        """Return all documented local-file candidates; never apply precedence."""

        leading = len(specifier) - len(specifier.lstrip("."))
        remainder = specifier[leading:]
        directory = posixpath.dirname(source_path)
        # TypeScript relative imports use ``./`` / ``../``; Python uses dots.
        if remainder.startswith("/"):
            base = posixpath.normpath(posixpath.join(directory, specifier))
            roots = [base]
        else:
            for _ in range(max(0, leading - 1)):
                directory = posixpath.dirname(directory)
            parts = [part for part in remainder.split(".") if part]
            roots = []
            # ``from .pkg import symbol`` is recorded as ``.pkg.symbol`` by the
            # current extractor.  Every module prefix is a candidate, rather
            # than assuming the final component is a module or symbol.
            for end in range(len(parts), 0, -1):
                roots.append(posixpath.join(directory, *parts[:end]))
        paths: set[str] = set()
        for root in roots:
            if root.endswith((".ts", ".tsx", ".py")):
                paths.add(root)
            else:
                paths.update(
                    {
                        f"{root}.ts",
                        f"{root}.tsx",
                        f"{root}.py",
                        f"{root}/index.ts",
                        f"{root}/index.tsx",
                        f"{root}/__init__.py",
                    }
                )
        return paths

    @staticmethod
    def _python_absolute_file_candidates(specifier: str) -> set[str]:
        root = specifier.replace(".", "/")
        return {f"{root}.py", f"{root}/__init__.py"}

    @staticmethod
    def _package_root(specifier: str, source_path: str) -> str:
        if source_path.endswith(".py"):
            return specifier.split(".", 1)[0]
        if specifier.startswith("@"):
            return "/".join(specifier.split("/")[:2])
        return specifier.split("/", 1)[0]

    def _reference_candidates(
        self,
        referent: str,
        source_path: str,
        nodes_by_key: dict[str, RiNode],
        bindings: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...] = (),
    ) -> list[RiNode]:
        """Return only targets a stored syntax fact uniquely proves.

        Evidence is considered in a fixed order: a full stable-key referent, a
        same-file top-level definition, then the explicit import bindings for the
        source file.  There is deliberately no repository-wide same-name
        fallback.  Without a same-file definition or an import binding, a lone
        symbol with the same name elsewhere is not proof; and when a binding
        exists but its module or exported symbol cannot be resolved, this returns
        no candidate (an unresolved diagnostic) rather than borrowing an
        unrelated same-named symbol.  Multiple binding targets stay ambiguous.
        """

        direct = nodes_by_key.get(referent)
        if direct is not None and direct.node_kind == "symbol":
            return [direct]
        same_file = nodes_by_key.get(f"{source_path}::{referent}")
        if same_file is not None and same_file.node_kind == "symbol":
            return [same_file]
        source = nodes_by_key.get(f"file:{source_path}")
        if source is None:
            return []
        bound_candidates: list[RiNode] = []
        for specifier, imported, local in bindings:
            if local != referent:
                continue
            for target_file in self._import_candidates(specifier, source_path, source, nodes_by_key):
                if target_file.node_kind != "file":
                    continue
                path = target_file.stable_key.removeprefix("file:")
                if imported == "default":
                    bound_candidates.extend(
                        node
                        for node in nodes_by_key.values()
                        if node.node_kind == "symbol"
                        and node.stable_key.startswith(f"{path}::")
                        and bool((node.properties or {}).get("default_export"))
                    )
                    continue
                direct_target = nodes_by_key.get(f"{path}::{imported}")
                if direct_target is not None and direct_target.node_kind == "symbol":
                    bound_candidates.append(direct_target)
                else:
                    bound_candidates.extend(
                        node
                        for node in nodes_by_key.values()
                        if node.node_kind == "symbol"
                        and node.name == imported
                        and node.stable_key.startswith(f"{path}::")
                    )
        return bound_candidates

    @staticmethod
    def _source_file(input_: _ObservedInput, nodes_by_key: dict[str, RiNode]) -> RiNode | None:
        subject = nodes_by_key.get(input_.observation.subject_key)
        if subject is not None and subject.node_kind == "file":
            return subject
        return nodes_by_key.get(f"file:{input_.evidence.path}")

    @staticmethod
    def _parse_import_binding(value: str | None) -> tuple[str, str, str] | None:
        if value is None:
            return None
        parts = value.split("|", 2)
        if len(parts) != 3 or not all(parts):
            return None
        return parts[0], parts[1], parts[2]

    @staticmethod
    def _containing_symbol(
        input_: _ObservedInput,
        nodes_by_key: dict[str, RiNode],
        evidence_by_node: dict[int, list[RiEvidence]],
    ) -> RiNode | None:
        candidates: list[tuple[int, str, RiNode]] = []
        for node in nodes_by_key.values():
            if node.node_kind != "symbol":
                continue
            for evidence in evidence_by_node.get(node.id, ()):
                if (
                    evidence.path == input_.evidence.path
                    and evidence.start_line <= input_.evidence.start_line
                    and evidence.end_line >= input_.evidence.end_line
                ):
                    candidates.append((evidence.end_line - evidence.start_line, node.stable_key, node))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            return None
        return candidates[0][2]

    def _add_edge(self, input_: _ObservedInput, subject: RiNode, predicate: str, object_: RiNode) -> None:
        snapshot = self._require_snapshot()
        self.store.add_edge(
            snapshot,
            subject_kind=subject.node_kind,
            subject_key=subject.stable_key,
            predicate=predicate,
            object_kind=object_.node_kind,
            object_key=object_.stable_key,
            producer=self.name,
            producer_version=self.version,
            evidence=(self._resolver_evidence(input_.evidence),),
            derived_from=({"kind": "observation", "observation_id": input_.observation.observation_id},),
        )

    def _unresolved(self, input_: _ObservedInput, message: str) -> tuple[int, int]:
        self._diagnostic(input_, RI_RES_UNRESOLVED, "unresolved reference", message)
        return 0, 1

    def _ambiguous(self, input_: _ObservedInput, message: str, candidates: tuple[str, ...]) -> tuple[int, int]:
        self._diagnostic(input_, RI_RES_AMBIGUOUS, "ambiguous resolution", message, candidates)
        return 0, 1

    def _diagnostic(
        self,
        input_: _ObservedInput,
        code: str,
        category: str,
        message: str,
        candidates: tuple[str, ...] = (),
    ) -> None:
        snapshot = self._require_snapshot()
        details: dict[str, object] = {"observation_id": input_.observation.observation_id}
        if candidates:
            details["candidates"] = sorted(candidates)
        self.store.add_diagnostic(
            snapshot,
            code=code,
            category=category,
            severity="warning",
            message=message,
            producer=self.producer,
            path=input_.evidence.path,
            span=(input_.evidence.start_line, input_.evidence.end_line),
            subject=input_.observation.subject_key,
            details=details,
        )

    def _resolver_evidence(self, evidence: RiEvidence) -> Evidence:
        return Evidence(
            path=evidence.path,
            start_line=evidence.start_line,
            end_line=evidence.end_line,
            extractor=self.name,
            extractor_version=self.version,
            logical_line_count=evidence.logical_line_count,
            granularity=evidence.granularity,
        )

    def _require_snapshot(self) -> RiSnapshot:
        if self._snapshot is None:
            raise RuntimeError("relationship resolver has no active snapshot")
        return self._snapshot

    @staticmethod
    def _evidence_key(evidence: RiEvidence) -> tuple[str, int, int, str, str, str]:
        return (
            evidence.path,
            evidence.start_line,
            evidence.end_line,
            evidence.granularity,
            evidence.extractor,
            evidence.extractor_version,
        )

    @staticmethod
    def _reference_input_key(input_: _ObservedInput) -> tuple[str, str | None, str, int, int, int]:
        return (
            input_.observation.subject_key,
            input_.observation.referent_text,
            input_.evidence.path,
            input_.evidence.start_line,
            input_.evidence.end_line,
            input_.observation.ordinal,
        )
