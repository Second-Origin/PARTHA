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


#: Well-known PyPI packages whose *import* name differs from the name they
#: are declared under (``import yaml`` <- ``pyyaml``). Without this a declared
#: ``pyjwt`` never matches ``import jwt`` and a normal import reads as an
#: undeclared package. Curated and bounded, like the other lists here; an
#: unlisted mismatch stays a finding, which is the conservative direction.
PYPI_DISTRIBUTIONS_BY_IMPORT_NAME: dict[str, tuple[str, ...]] = {
    "yaml": ("pyyaml",),
    "jwt": ("pyjwt",),
    "argon2": ("argon2-cffi",),
    "PIL": ("pillow",),
    "cv2": ("opencv-python", "opencv-python-headless"),
    "bs4": ("beautifulsoup4",),
    "sklearn": ("scikit-learn",),
    "dateutil": ("python-dateutil",),
    "dotenv": ("python-dotenv",),
    "jose": ("python-jose",),
    "multipart": ("python-multipart",),
    "magic": ("python-magic",),
    "git": ("gitpython",),
    "attr": ("attrs",),
    "psycopg2": ("psycopg2-binary",),
    "OpenSSL": ("pyopenssl",),
    "serial": ("pyserial",),
    "markdown": ("markdown",),
    "google.protobuf": ("protobuf",),
}


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
    if key is not None and key in declared_dependency_keys:
        return True
    if source_path.endswith(".py") and not specifier.startswith("."):
        root = package_root(specifier, source_path)
        return any(
            dependency_stable_key("pypi", distribution) in declared_dependency_keys
            for distribution in PYPI_DISTRIBUTIONS_BY_IMPORT_NAME.get(root, ())
        )
    return False


#: Extensions a TS/JS module specifier may omit, and asset/style files a
#: bundler lets you import by their full name.
_JS_MODULE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")

#: Conventional "project root" import prefixes (tsconfig/vite ``paths``). The
#: prefix names the source root of the *importing* package, which is an
#: in-repo location, not a package published elsewhere.
_JS_ALIAS_PREFIXES = ("@/", "~/", "#/")


def resolves_to_in_repo_file(
    specifier: str,
    source_path: str,
    file_paths: frozenset[str],
    directory_paths: frozenset[str] = frozenset(),
) -> bool:
    """True if an import specifier the resolver left unresolved plainly names
    a file that *is* in the scanned repository.

    Two shapes the resolver does not link, both of which point at real
    in-repo files: a TS/JS path alias (``@/lib/utils`` -> ``<pkg>/src/lib/
    utils.ts``, or a directory of scanned files) and a Python absolute import whose package root is a
    sub-directory of the repo (``app.api.deps`` from ``backend/app/...`` ->
    ``backend/app/api/deps.py``). The target must sit under a directory that
    is an ancestor of the importing file, so a same-named file in an
    unrelated package never counts.

    Read-time only, like the rest of this module: it decides whether an
    unresolved fact is a defect of the reviewed repository, never whether it
    resolves.
    """

    if not specifier or not source_path or not file_paths:
        return False
    if source_path.endswith(".py"):
        return _python_module_in_repo(specifier, source_path, file_paths)
    if source_path.endswith(_JS_MODULE_EXTENSIONS):
        return _js_alias_in_repo(specifier, source_path, file_paths, directory_paths)
    return False


def _ancestor_prefixes(source_path: str) -> list[str]:
    """``""`` plus every directory prefix of ``source_path``, with trailing
    slash: ``a/b/c.ts`` -> ``["", "a/", "a/b/"]``."""

    segments = source_path.split("/")[:-1]
    return ["/".join(segments[:count]) + "/" if count else "" for count in range(len(segments) + 1)]


def _python_module_in_repo(specifier: str, source_path: str, file_paths: frozenset[str]) -> bool:
    if specifier.startswith("."):
        return False
    parts = specifier.split(".")
    prefixes = _ancestor_prefixes(source_path)
    # ``app.api.deps.SessionDep`` names a symbol inside module ``app.api.deps``,
    # so try the full dotted path first and then progressively shorter ones.
    for end in range(len(parts), 0, -1):
        module = "/".join(parts[:end])
        for prefix in prefixes:
            if f"{prefix}{module}.py" in file_paths or f"{prefix}{module}/__init__.py" in file_paths:
                return True
    return False


def _js_alias_in_repo(
    specifier: str,
    source_path: str,
    file_paths: frozenset[str],
    directory_paths: frozenset[str],
) -> bool:
    alias = next((prefix for prefix in _JS_ALIAS_PREFIXES if specifier.startswith(prefix)), None)
    if alias is None:
        return False
    target = specifier[len(alias) :].split("?", 1)[0].rstrip("/")
    if not target:
        return False
    tails = [target]
    tails += [target + extension for extension in _JS_MODULE_EXTENSIONS]
    tails += [f"{target}/index{extension}" for extension in _JS_MODULE_EXTENSIONS]
    # A path alias roots at the importing package's ``src`` directory (or the
    # package root itself); accept either as the anchor.
    for prefix in _ancestor_prefixes(source_path):
        for tail in tails:
            if f"{prefix}src/{tail}" in file_paths or f"{prefix}{tail}" in file_paths:
                return True
        # A barrel (``index.ts`` holding only re-exports) leaves no node or
        # evidence of its own, so a directory that holds scanned files is the
        # available proof that ``@/shared/services/api`` names real code.
        if f"{prefix}src/{target}" in directory_paths or f"{prefix}{target}" in directory_paths:
            return True
    return False


#: Files a bundler lets you import that are not code: stylesheets, images,
#: fonts, media. Importing one is a build-time reference, not a relationship
#: between code files.
_NON_CODE_ASSET_EXTENSIONS = frozenset(
    {
        ".css", ".scss", ".sass", ".less", ".styl",
        ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".bmp",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".mp3", ".mp4", ".webm", ".ogg", ".wav",
        ".md", ".mdx", ".txt", ".csv", ".yaml", ".yml", ".graphql", ".gql",
    }
)  # fmt: skip


def is_non_code_asset_import(specifier: str, source_path: str) -> bool:
    """True if a TS/JS import names a non-code asset, or uses a bundler loader
    query (``./generated.ts?raw``, ``./icon.svg?url``), which imports the file
    as text/URL rather than as a module."""

    if not source_path.endswith(_JS_MODULE_EXTENSIONS):
        return False
    base, has_query, _ = specifier.partition("?")
    if has_query:
        return True
    return "." in base.rsplit("/", 1)[-1] and "." + base.rsplit(".", 1)[-1].lower() in _NON_CODE_ASSET_EXTENSIONS
