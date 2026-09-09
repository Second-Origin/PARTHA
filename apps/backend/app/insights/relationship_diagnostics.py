"""Split ``RI-RES-UNRESOLVED`` diagnostics into real gaps vs. external references.

The relationship resolver is deliberately strict: a reference it cannot prove
points at an in-repo symbol becomes an ``RI-RES-UNRESOLVED`` warning rather than
a guessed edge (see ``docs/architecture/REPOSITORY_INTELLIGENCE_RESOLUTION.md``).
That is correct, honest data and it stays in the sealed graph untouched.

But most of those warnings, on any real repository, are not coverage gaps at
all -- they are calls into a third-party dependency (``jsonify``, ``MagicMock``,
``useState``) or the language platform (``Path``, ``SimpleNamespace``), and an
``import`` of a package the repo actually declares or of the standard library.
There is nothing in-repo for the resolver to point those at, and nothing wrong.
Counting all of them together under one "Unresolved relationships" number makes
a healthy analysis look broken.

This module applies the same "this identifier plainly belongs to the
language/platform, not to this repository" judgment the review layer already
uses for unresolved imports (``app/review/import_dispositions.py``, #412),
extended to bare-name reference observations via their file's import bindings,
so repository-insights can report the genuine in-repo gap count on its own.
It changes no stored fact -- only how the read-time metric is bucketed.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass

from app.review.import_dispositions import is_recognized_external_import

#: Observation kinds that record a bare referenced name whose binding (if any)
#: is an ``import_binding`` for the same source file. ``import`` is handled
#: separately (its own referent already *is* the module specifier).
_REFERENCE_KINDS = frozenset({"call", "implements", "injects", "route_handler"})

#: A bare call to one of these, with no import binding, is a call into the
#: language itself, not a missing in-repo definition. Mirrors the extraction
#: layer's own builtin skip (``app/extraction/python.py``, #392); repeated
#: here so an already-sealed snapshot from before that fix -- whose bare
#: ``len`` / ``print`` / ``str`` calls are already recorded -- still reads
#: sensibly at insights time.
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
    }
)


def _is_platform_reference(name: str, source_path: str) -> bool:
    """True if a bare, unbound call name belongs to the language/host itself."""

    if source_path.endswith(".py"):
        return name in _PYTHON_BUILTIN_NAMES
    if source_path.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
        return name in _JS_AMBIENT_GLOBAL_NAMES
    return False


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

    @property
    def total(self) -> int:
        return self.in_repo_gap + self.external_reference


def split_unresolved_relationships(
    *,
    diagnostics: list[tuple[str | None, str | None]],
    observed_kind_by_observation: dict[str, str],
    referent_by_observation: dict[str, str | None],
    import_specifier_by_local_name: dict[str, dict[str, str]],
    declared_dependency_keys: frozenset[str],
) -> UnresolvedRelationshipSplit:
    """Bucket each ``RI-RES-UNRESOLVED`` diagnostic.

    ``diagnostics`` is ``(source_path, observation_id)`` per diagnostic.
    ``import_specifier_by_local_name`` maps a source path to that file's
    ``{local name: module specifier}`` import bindings. A diagnostic whose
    originating observation cannot be found, or whose kind carries no usable
    referent, is counted as an in-repo gap -- the conservative direction.
    """

    in_repo_gap = 0
    external_reference = 0
    for source_path, observation_id in diagnostics:
        if _is_external_reference(
            source_path=source_path,
            kind=observed_kind_by_observation.get(observation_id or ""),
            referent=referent_by_observation.get(observation_id or ""),
            import_specifier_by_local_name=import_specifier_by_local_name,
            declared_dependency_keys=declared_dependency_keys,
        ):
            external_reference += 1
        else:
            in_repo_gap += 1
    return UnresolvedRelationshipSplit(in_repo_gap=in_repo_gap, external_reference=external_reference)


def _is_external_reference(
    *,
    source_path: str | None,
    kind: str | None,
    referent: str | None,
    import_specifier_by_local_name: dict[str, dict[str, str]],
    declared_dependency_keys: frozenset[str],
) -> bool:
    if not source_path:
        return False
    if kind == "import":
        if not referent:
            return False
        return is_recognized_external_import(referent, source_path, declared_dependency_keys)
    if kind in _REFERENCE_KINDS and referent:
        specifier = import_specifier_by_local_name.get(source_path, {}).get(referent)
        if specifier is None:
            return _is_platform_reference(referent, source_path)
        return is_recognized_external_import(specifier, source_path, declared_dependency_keys)
    return False
