"""Disposition for unresolved ``import``-kind ``RI-RES-UNRESOLVED`` diagnostics.

Importing a standard-library module, or a package the repository actually
declares as a dependency, is normal code — not a gap worth a review finding.
The resolver correctly leaves it unresolved either way, because it isn't
part of the *scanned* repository and there is nothing in-repo to point an
edge at; that stays true, honest data. This module decides, at review time
only, whether that unresolved fact should be *promoted* to a finding: never
whether it resolves. A relative import, or a bare specifier that is neither
stdlib/builtin nor a declared dependency, still looks like it should be a
same-repo reference and stays a finding — that is the genuine case (a typo,
a missing dependency declaration, or a real extractor gap).

Mirrors the builtin-call-noise fix at the extraction layer: same "this
identifier plainly belongs to the language/platform, not to this repository"
judgment, applied to import specifiers instead of bare calls.
"""

from __future__ import annotations

import sys

from app.extraction.naming import dependency_stable_key, package_root

#: The running interpreter's own standard library, used as the reference set
#: the same way extraction/python.py's builtin-call skip uses ``dir(builtins)``
#: -- an approximation of "the language/platform," not a per-repo Python
#: version lookup. Available from Python 3.10.
PYTHON_STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)

#: Node.js builtin modules (https://nodejs.org/api/), importable bare or with
#: an explicit ``node:`` prefix. Curated the same way extraction/typescript.py
#: curates ``_GLOBAL_CALL_NAMES`` for globals -- a bounded, documented list,
#: not a runtime introspection (there is no Node runtime to introspect here).
NODE_BUILTIN_MODULES: frozenset[str] = frozenset(
    {
        "assert",
        "async_hooks",
        "buffer",
        "child_process",
        "cluster",
        "console",
        "constants",
        "crypto",
        "dgram",
        "diagnostics_channel",
        "dns",
        "domain",
        "events",
        "fs",
        "http",
        "http2",
        "https",
        "inspector",
        "module",
        "net",
        "os",
        "path",
        "perf_hooks",
        "process",
        "punycode",
        "querystring",
        "readline",
        "repl",
        "stream",
        "string_decoder",
        "test",
        "timers",
        "tls",
        "trace_events",
        "tty",
        "url",
        "util",
        "v8",
        "vm",
        "wasi",
        "worker_threads",
        "zlib",
    }
)


def is_platform_import(specifier: str, source_path: str) -> bool:
    """True if ``specifier``'s package root is stdlib (Python) or a Node
    builtin (TypeScript/JavaScript) -- language/platform, never this repo."""

    if specifier.startswith("."):
        return False
    root = package_root(specifier, source_path)
    if not root:
        return False
    if source_path.endswith(".py"):
        return root in PYTHON_STDLIB_MODULES
    return root in NODE_BUILTIN_MODULES or root.removeprefix("node:") in NODE_BUILTIN_MODULES


def declared_dependency_key(specifier: str, source_path: str) -> str | None:
    """The dependency stable key ``specifier`` would need to match against a
    declared, sealed-snapshot dependency node -- or ``None`` if it can never
    be an external dependency, which must stay eligible to be a genuine
    finding: a relative import (``package_root`` reduces one to ``""`` for
    Python, but only to ``"."``/``".."`` for JS/TS -- checked explicitly
    here rather than relying on no real npm package ever being named that),
    or a specifier with no package root at all.
    """

    if specifier.startswith("."):
        return None
    root = package_root(specifier, source_path)
    if not root:
        return None
    ecosystem = "pypi" if source_path.endswith(".py") else "npm"
    return dependency_stable_key(ecosystem, root)


def is_recognized_external_import(
    specifier: str,
    source_path: str,
    declared_dependency_keys: frozenset[str],
) -> bool:
    """True if this unresolved import's target is a recognized external
    dependency (stdlib/builtin, or declared in the repo's own manifest) --
    the case that should never surface as a finding."""

    if is_platform_import(specifier, source_path):
        return True
    key = declared_dependency_key(specifier, source_path)
    return key is not None and key in declared_dependency_keys
