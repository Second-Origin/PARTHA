"""Heuristic role classification over a building RI snapshot (#95).

This producer never reads the repository working tree or reparses source: it
reads only facts a snapshot already has (file/symbol nodes and resolved
``injects`` edges) and emits ``classified_as`` assertions naming the semantic
role a file or symbol plays (service, model, controller, middleware, ...), or
flags a dependency-injected function as an authentication guard.

Every emitted assertion is ``truth_class="inferred"`` with a
``"confidence": "heuristic"`` value, so a heuristic classification can never
be mistaken for an observed fact (CONTRIBUTING.md rule: heuristic results must
not be presented as guaranteed facts). A file or symbol that matches no rule
gets no assertion at all — silence, not a fabricated "unknown" classification.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from sqlalchemy import select

from app.intelligence.snapshot_store import SnapshotStateError, SnapshotStore, node_ref
from app.models.snapshot import RiEdge, RiNode, RiSnapshot

_FILE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(^|/)readme", re.IGNORECASE), "documentation"),
    (re.compile(r"(^|/)(test|spec|__tests__)", re.IGNORECASE), "test"),
    (re.compile(r"(^|/)(main|app|index)\.(py|ts|tsx|js|jsx)$", re.IGNORECASE), "entrypoint"),
    (re.compile(r"middleware", re.IGNORECASE), "middleware"),
    (re.compile(r"(/controllers?/|controller)", re.IGNORECASE), "controller"),
    (re.compile(r"(/routes?/|/api/|route)", re.IGNORECASE), "route"),
    (re.compile(r"(/services?/|service)", re.IGNORECASE), "service"),
    (re.compile(r"(/repositories?/|repository|repo)", re.IGNORECASE), "repository"),
    (re.compile(r"(/models?/|/schemas?/|model)", re.IGNORECASE), "model"),
    (re.compile(r"dto", re.IGNORECASE), "dto"),
    (re.compile(r"interface", re.IGNORECASE), "interface"),
    (re.compile(r"enum", re.IGNORECASE), "enum"),
    (re.compile(r"(/config|settings)", re.IGNORECASE), "configuration"),
    (re.compile(r"(/utils?/|/lib/|util)", re.IGNORECASE), "utility"),
)

_SYMBOL_SUFFIX_RULES: tuple[tuple[str, str], ...] = (
    ("Middleware", "middleware"),
    ("Service", "service"),
    ("Repository", "repository"),
    ("Controller", "controller"),
    ("Model", "model"),
    ("DTO", "dto"),
    ("Dto", "dto"),
)

_AUTH_DEPENDENCY_PATTERN = re.compile(
    r"(auth|current_user|credential|token|permission|require_user|verify|oauth)",
    re.IGNORECASE,
)


def _file_role(path: str) -> str | None:
    for pattern, role in _FILE_RULES:
        if pattern.search(path):
            return role
    return None


def _symbol_role(name: str) -> str | None:
    for suffix, role in _SYMBOL_SUFFIX_RULES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return role
    return None


class RoleClassifier:
    """Classify file and symbol facts already persisted in a building snapshot."""

    name = "role-classifier"
    version = "1.0.0"

    def __init__(self, store: SnapshotStore) -> None:
        self.store = store

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def classify(
        self,
        snapshot: RiSnapshot,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> int:
        """Add every resolvable classification assertion to one building snapshot.

        Returns the number of assertions attempted (existing matching
        assertions are consolidated by :class:`SnapshotStore`, so this is a
        count of attempted facts, not a row count).
        """

        self._check_cancelled(check_cancelled)
        if snapshot.state != "building":
            raise SnapshotStateError("role classification requires a building snapshot")
        if self.producer not in set(snapshot.producer_version_set):
            raise ValueError(f"snapshot producer_version_set is missing {self.producer!r}")

        nodes = list(
            self.store.db.scalars(
                select(RiNode).where(RiNode.snapshot_id == snapshot.snapshot_id)
            )
        )
        injected_keys = {
            edge.object_key
            for edge in self.store.db.scalars(
                select(RiEdge).where(
                    RiEdge.snapshot_id == snapshot.snapshot_id,
                    RiEdge.predicate == "injects",
                )
            )
        }

        assertions_added = 0
        for node in nodes:
            self._check_cancelled(check_cancelled)
            if node.node_kind == "file" and node.stable_key.startswith("file:"):
                role = _file_role(node.stable_key.removeprefix("file:"))
                if role is not None:
                    self._assert_classification(snapshot, node, role)
                    assertions_added += 1
            elif node.node_kind == "symbol" and node.name:
                role = _symbol_role(node.name)
                if role is not None:
                    self._assert_classification(snapshot, node, role)
                    assertions_added += 1
                if node.stable_key in injected_keys and _AUTH_DEPENDENCY_PATTERN.search(node.name):
                    self._assert_classification(snapshot, node, "auth_dependency")
                    assertions_added += 1
        return assertions_added

    def _assert_classification(self, snapshot: RiSnapshot, node: RiNode, role: str) -> None:
        self.store.add_assertion(
            snapshot,
            subject_kind=node.node_kind,
            subject_key=node.stable_key,
            predicate="classified_as",
            value={"classification": role, "confidence": "heuristic"},
            producer=self.name,
            producer_version=self.version,
            derived_from=(node_ref(node.stable_key),),
        )

    @staticmethod
    def _check_cancelled(check_cancelled: Callable[[], None] | None) -> None:
        if check_cancelled is not None:
            check_cancelled()
