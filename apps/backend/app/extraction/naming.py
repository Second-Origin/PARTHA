from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from collections.abc import Sequence

from app.intelligence import canonical


def dependency_stable_key(ecosystem: str, name: str) -> str:
    """Build the logical ``dep:<ecosystem>:<name>`` identity (RFC §4.3).

    This is the single place a dependency identity is derived. A direct manifest
    declaration and a lockfile resolution describe *one* logical dependency, so
    both producers must land on a byte-identical key or they would create two
    nodes for one entity. PyPI names are folded per PEP 503 (runs of ``-``,
    ``_``, and ``.`` collapse to ``-``, lowercased) so ``Foo_Bar`` declared in a
    manifest and ``foo-bar`` pinned in a lockfile share one node. npm names are
    already canonical and are used verbatim.
    """

    if ecosystem == "pypi":
        name = re.sub(r"[-_.]+", "-", name).lower()
    return canonical.normalize_stable_key("dependency", f"dep:{ecosystem}:{name}")


def service_stable_key(origin: str) -> str:
    """Build the ``svc:<origin>`` identity for an observed outbound service.

    Identity is the normalized origin only — scheme, host, and a non-default
    port. Request paths, query strings, and methods vary per call site and are
    recorded on the call's own observation, so folding them into the node key
    would create one "service" per URL instead of one per destination.
    """

    return canonical.normalize_stable_key("service", f"svc:{origin}")


def iac_resource_stable_key(manifest_path: str, resource_type: str, name: str) -> str:
    """Build the ``iac:<manifest-path>::<type>/<name>`` identity (RFC §4.3).

    An IaC resource is only unique within the manifest that declares it: two
    Compose files may both declare a ``db`` service and they are different
    resources, so the manifest path is part of the identity rather than a
    property alone.
    """

    normalized = canonical.normalize_repo_path(manifest_path)
    return canonical.normalize_stable_key("iac_resource", f"iac:{normalized}::{resource_type}/{name}")


def symbol_stable_key(path: str, scope: Sequence[str], name: str) -> str:
    """Build ``<file-path>::<qualified.name>`` (RFC §4.3), path normalized."""

    normalized = canonical.normalize_repo_path(path)
    qualified = ".".join([*scope, name])
    return f"{normalized}::{qualified}"


def module_stable_key(path: str) -> str:
    """Build the directory-scoped ``mod:<directory>`` key (RFC §4.3)."""

    directory = posixpath.dirname(canonical.normalize_repo_path(path))
    return canonical.normalize_stable_key("module", f"mod:{directory}")


def package_root(specifier: str, source_path: str) -> str:
    """The top-level package name a module specifier would be published under.

    Shared by the resolver (matching an import against a declared dependency
    node) and the review layer (deciding whether an unresolved import's
    target is a recognized external package rather than a broken internal
    reference) so the two never independently drift on what "the package"
    means for a given specifier.

    A Python specifier is always dotted (``django.core.wsgi``,
    ``.models.User`` for a relative import) — the root is everything before
    the first ``.``, which is empty for a relative import, correctly ruling
    it out as an external package. A JS/TS specifier is slash-separated; a
    scoped package's root is its first two segments (``@scope/name``), an
    unscoped or relative one's is its first (``react``, ``./util``).
    """

    if source_path.endswith(".py"):
        return specifier.split(".", 1)[0]
    if specifier.startswith("@"):
        return "/".join(specifier.split("/")[:2])
    return specifier.split("/", 1)[0]


def module_name(path: str) -> str | None:
    """Name a module after its directory, not the file that evidenced it.

    The key is directory-scoped, so every file in a directory must produce a
    byte-identical module record — naming it after the file would make sibling
    modules conflicting records for one key and the snapshot would refuse to
    seal. The repository root has no meaningful short name.
    """

    directory = posixpath.dirname(canonical.normalize_repo_path(path))
    return posixpath.basename(directory) or None


class DiscriminatorAssigner:
    """Assigns RFC §4.3 ``#<n>`` discriminators by source order within one file.

    The first occurrence of a base symbol key is returned unchanged; each later
    occurrence gets ``#2``, ``#3``, … The second return value is ``True`` when a
    discriminator was appended, so the caller can emit an ``RI-KEY-DUP-SYMBOL``
    diagnostic. Instantiate one per file so counters are revision-local.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)

    def key(self, base_symbol_key: str) -> tuple[str, bool]:
        self._counts[base_symbol_key] += 1
        n = self._counts[base_symbol_key]
        if n == 1:
            return base_symbol_key, False
        return f"{base_symbol_key}#{n}", True
