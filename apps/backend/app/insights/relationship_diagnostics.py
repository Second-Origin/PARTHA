"""Tell a real relationship gap apart from a reference into external code.

The relationship resolver is deliberately strict: a reference it cannot prove
points at an in-repo symbol becomes an ``RI-RES-UNRESOLVED`` warning rather than
a guessed edge (see ``docs/architecture/REPOSITORY_INTELLIGENCE_RESOLUTION.md``).
That is correct, honest data and it stays in the sealed graph untouched.

But most of those warnings, on any real repository, are not coverage gaps at
all -- they are calls into a third-party dependency (``jsonify``, ``MagicMock``,
``useState``) or the language platform (``Path``, ``SimpleNamespace``, ``len``),
and imports of packages the repo actually declares or of the standard library.
There is nothing in-repo for the resolver to point those at, and nothing wrong.
Surfacing all of them together -- as one "Unresolved relationships" number in
Repository Insights, or as a red module badge and a giant diagnostics list on
the Architecture page -- makes a healthy analysis look broken.

This module applies the same "this identifier plainly belongs to the
language/platform, not to this repository" judgment the review layer already
uses for unresolved imports (``app/review/import_dispositions.py``, #412),
extended to bare-name reference observations via their file's import bindings.
Read-time only: it changes no stored fact.

This is the one place that judgment lives. Repository Insights, the
Architecture view and the Engineering Review all consult it, so they cannot
disagree about whether the same diagnostic is a problem; each consumer only
decides what to do with a disposition (see :class:`UnresolvedDisposition`).
"""

from __future__ import annotations

import builtins
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.snapshot import RiEvidence, RiNode, RiObservation
from app.review.import_dispositions import (
    is_non_code_asset_import,
    is_recognized_external_import,
    resolves_to_in_repo_file,
)

#: Observation kinds that record a bare referenced name whose binding (if any)
#: is an ``import_binding`` for the same source file. ``import`` is handled
#: separately (its own referent already *is* the module specifier).
_REFERENCE_KINDS = frozenset({"call", "implements", "injects", "route_handler"})

#: A bare call to one of these, with no import binding, is a call into the
#: language itself, not a missing in-repo definition. Mirrors the extraction
#: layer's own builtin skip (``app/extraction/python.py``, #392); repeated
#: here so an already-sealed snapshot from before that fix -- whose bare
#: ``len`` / ``print`` / ``str`` calls are already recorded -- still reads
#: sensibly at read time.
_PYTHON_BUILTIN_NAMES: frozenset[str] = frozenset(name for name in dir(builtins) if not name.startswith("_"))

#: JS/TS globals that are called but never imported: test-runner injections
#: and a few ubiquitous host objects. A curated, documented list in the same
#: spirit as ``import_dispositions.NODE_BUILTIN_MODULES`` -- there is no
#: runtime to introspect.
_JS_AMBIENT_GLOBAL_NAMES: frozenset[str] = frozenset(
    {
        "describe",
        "it",
        "test",
        "expect",
        "beforeAll",
        "beforeEach",
        "afterAll",
        "afterEach",
        "vi",
        "jest",
        "waitFor",
        "within",
        "fireEvent",
        "fetch",
        "structuredClone",
        "queueMicrotask",
        "requestAnimationFrame",
        "cancelAnimationFrame",
        "setTimeout",
        "clearTimeout",
        "setInterval",
        "clearInterval",
        "alert",
        "confirm",
        "prompt",
        "getComputedStyle",
        "matchMedia",
        "requestIdleCallback",
        "atob",
        "btoa",
    }
)


#: The resolver's message for a call whose name a local variable/parameter
#: shadows (``app/intelligence/resolution.py``). Matched by text because the
#: diagnostic carries no other marker; a test drives a real analysis through
#: it so a wording change fails loudly instead of silently reviving the noise.
SHADOWED_CALL_MESSAGE = "calls target is shadowed by a local binding"


class UnresolvedDisposition(StrEnum):
    """What an ``RI-RES-UNRESOLVED`` diagnostic actually is."""

    #: The target is the language platform, the standard library, or a package
    #: the repository declares. Nothing in-repo to point at; nothing wrong.
    EXTERNAL = "external"
    #: The name is a local variable or parameter, not a cross-file relationship.
    LOCAL_BINDING = "local-binding"
    #: The specifier names a file that exists in the repository (a path alias,
    #: or an absolute import from a sub-directory package root). The
    #: relationship is real and unlinked: a limit of the analysis, not a
    #: defect in the reviewed code.
    IN_REPO_TARGET_EXISTS = "in-repo-target-exists"
    #: An import of a stylesheet, image or other non-code asset (or a bundler
    #: loader query such as ``?raw``). Not a code relationship.
    NON_CODE_ASSET = "non-code-asset"
    #: Expected to resolve in the repository and could not be explained.
    GAP = "gap"


@dataclass(frozen=True)
class UnresolvedRelationshipContext:
    """Everything needed to classify one snapshot's ``RI-RES-UNRESOLVED``
    diagnostics, loaded once per read.

    ``observation_id`` here is the sealed ``RiObservation.observation_id``
    string carried in a diagnostic's ``details['observation_id']``.
    """

    observed_kind_by_observation: dict[str, str]
    referent_by_observation: dict[str, str | None]
    #: source path -> {local name: module specifier} from that file's import bindings
    import_specifier_by_local_name: dict[str, dict[str, str]]
    declared_dependency_keys: frozenset[str]
    #: Every scanned file path (``file:`` nodes), for "does this specifier name
    #: a file that is in the repository" checks.
    file_paths: frozenset[str] = frozenset()
    #: Every directory (as a path, no trailing slash) that holds a scanned file.
    directory_paths: frozenset[str] = frozenset()

    @classmethod
    def empty(cls) -> UnresolvedRelationshipContext:
        return cls({}, {}, {}, frozenset())


@dataclass(frozen=True)
class UnresolvedRelationshipSplit:
    """Counts for one snapshot's ``RI-RES-UNRESOLVED`` diagnostics."""

    #: References PARTHA expected to resolve within the repository but could
    #: not -- a relative import that matched no file, a bare name with no
    #: binding and no same-file definition, a shadowed call. The signal worth
    #: surfacing.
    in_repo_gap: int
    #: References whose target is the standard library / language platform or
    #: a package the repository declares as a dependency. Expected, not a gap.
    external_reference: int
    #: Calls to a local variable or parameter. Not a relationship at all.
    local_binding: int = 0
    #: Imports of stylesheets, images and other non-code assets.
    non_code_asset: int = 0

    @property
    def total(self) -> int:
        return self.in_repo_gap + self.external_reference + self.local_binding + self.non_code_asset


def load_unresolved_relationship_context(db: Session, snapshot_id: str) -> UnresolvedRelationshipContext:
    """Read the observation / import-binding / dependency facts for one snapshot.

    Sealed rows only; nothing here mutates or interprets the graph.
    """

    observed_kind_by_observation: dict[str, str] = {}
    referent_by_observation: dict[str, str | None] = {}
    binding_referent_by_pk: dict[int, str] = {}
    for pk, observation_id, kind, referent in db.execute(
        select(
            RiObservation.id,
            RiObservation.observation_id,
            RiObservation.observed_kind,
            RiObservation.referent_text,
        ).where(RiObservation.snapshot_id == snapshot_id)
    ).all():
        observed_kind_by_observation[observation_id] = kind
        referent_by_observation[observation_id] = referent
        if kind == "import_binding" and referent:
            binding_referent_by_pk[pk] = referent

    # An import_binding's own subject_key is directory-scoped for Python, so its
    # evidence path is the only exact source-file link. One join keeps this to
    # the binding rows regardless of how many imports the repo has.
    import_specifier_by_local_name: dict[str, dict[str, str]] = defaultdict(dict)
    if binding_referent_by_pk:
        for observation_ref, path in db.execute(
            select(RiEvidence.observation_ref, RiEvidence.path)
            .join(RiObservation, RiObservation.id == RiEvidence.observation_ref)
            .where(
                RiEvidence.snapshot_id == snapshot_id,
                RiObservation.observed_kind == "import_binding",
            )
        ).all():
            referent = binding_referent_by_pk.get(observation_ref)
            if referent is None or not path:
                continue
            parts = referent.split("|", 2)
            if len(parts) == 3 and parts[0] and parts[2]:
                import_specifier_by_local_name[path].setdefault(parts[2], parts[0])

    declared_dependency_keys = frozenset(
        db.scalars(
            select(RiNode.stable_key).where(
                RiNode.snapshot_id == snapshot_id,
                RiNode.node_kind == "dependency",
            )
        ).all()
    )

    # A file that only re-exports (a barrel ``index.ts``) yields no file node,
    # but its statements still leave evidence at its path, so both count as
    # "this path was scanned".
    file_paths = {
        key.removeprefix("file:")
        for key in db.scalars(
            select(RiNode.stable_key).where(
                RiNode.snapshot_id == snapshot_id,
                RiNode.node_kind == "file",
            )
        ).all()
        if key.startswith("file:")
    }
    file_paths.update(
        path
        for path in db.scalars(select(RiEvidence.path).where(RiEvidence.snapshot_id == snapshot_id).distinct()).all()
        if path
    )

    return UnresolvedRelationshipContext(
        observed_kind_by_observation=observed_kind_by_observation,
        referent_by_observation=referent_by_observation,
        import_specifier_by_local_name=dict(import_specifier_by_local_name),
        declared_dependency_keys=declared_dependency_keys,
        file_paths=frozenset(file_paths),
        directory_paths=frozenset(
            "/".join(parts[:count])
            for parts in (path.split("/") for path in file_paths)
            for count in range(1, len(parts))
        ),
    )


def classify_unresolved(
    source_path: str | None,
    observation_id: str | None,
    ctx: UnresolvedRelationshipContext,
    message: str | None = None,
) -> UnresolvedDisposition:
    """Judge one ``RI-RES-UNRESOLVED`` diagnostic.

    Unknown observation, missing path, or a kind that carries no usable
    referent all return ``GAP`` -- the conservative direction (treat it as a
    real gap).
    """

    if not source_path:
        return UnresolvedDisposition.GAP
    if message == SHADOWED_CALL_MESSAGE:
        return UnresolvedDisposition.LOCAL_BINDING
    kind = ctx.observed_kind_by_observation.get(observation_id or "")
    referent = ctx.referent_by_observation.get(observation_id or "")
    if not referent:
        return UnresolvedDisposition.GAP
    if kind == "import":
        specifier = referent
    elif kind in _REFERENCE_KINDS:
        bound = ctx.import_specifier_by_local_name.get(source_path, {}).get(referent)
        if bound is None:
            if _is_platform_reference(referent, source_path):
                return UnresolvedDisposition.EXTERNAL
            return UnresolvedDisposition.GAP
        specifier = bound
    else:
        return UnresolvedDisposition.GAP
    if is_recognized_external_import(specifier, source_path, ctx.declared_dependency_keys):
        return UnresolvedDisposition.EXTERNAL
    if is_non_code_asset_import(specifier, source_path):
        return UnresolvedDisposition.NON_CODE_ASSET
    if resolves_to_in_repo_file(specifier, source_path, ctx.file_paths, ctx.directory_paths):
        return UnresolvedDisposition.IN_REPO_TARGET_EXISTS
    return UnresolvedDisposition.GAP


def is_external_unresolved(
    source_path: str | None,
    observation_id: str | None,
    ctx: UnresolvedRelationshipContext,
) -> bool:
    """True if this diagnostic is a reference into external / platform code."""

    return classify_unresolved(source_path, observation_id, ctx) is UnresolvedDisposition.EXTERNAL


def split_unresolved_relationships(
    diagnostics: list[tuple[str | None, str | None, str | None]],
    ctx: UnresolvedRelationshipContext,
) -> UnresolvedRelationshipSplit:
    """Bucket every ``RI-RES-UNRESOLVED`` diagnostic.

    ``diagnostics`` is ``(source_path, observation_id, message)`` per
    diagnostic. A relationship the analysis could not link although its target
    file exists still counts as an in-repo gap here: it is a real coverage
    limit worth showing, just not a defect of the reviewed code.
    """

    in_repo_gap = 0
    external_reference = 0
    local_binding = 0
    non_code_asset = 0
    for source_path, observation_id, message in diagnostics:
        disposition = classify_unresolved(source_path, observation_id, ctx, message)
        if disposition is UnresolvedDisposition.EXTERNAL:
            external_reference += 1
        elif disposition is UnresolvedDisposition.LOCAL_BINDING:
            local_binding += 1
        elif disposition is UnresolvedDisposition.NON_CODE_ASSET:
            non_code_asset += 1
        else:
            in_repo_gap += 1
    return UnresolvedRelationshipSplit(
        in_repo_gap=in_repo_gap,
        external_reference=external_reference,
        local_binding=local_binding,
        non_code_asset=non_code_asset,
    )


def _is_platform_reference(name: str, source_path: str) -> bool:
    """True if a bare, unbound call name belongs to the language/host itself."""

    if source_path.endswith(".py"):
        return name in _PYTHON_BUILTIN_NAMES
    if source_path.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
        return name in _JS_AMBIENT_GLOBAL_NAMES
    return False
