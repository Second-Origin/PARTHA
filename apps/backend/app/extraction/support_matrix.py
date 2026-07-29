"""The authoritative, typed capability registry for Repository Intelligence.

The registry deliberately lives beside the production extractors.  Benchmark
taxonomy is allowed to describe fixture variants, but it does not decide what
the product supports.  ``SUPPORT_MATRIX`` remains as a compatibility view for
existing extractor tests and callers; its contents are derived from the
registry below.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable


REGISTRY_SCHEMA_VERSION = "ri-capability-registry.v1"
README_CAPABILITIES_START = "<!-- BEGIN GENERATED CAPABILITY REGISTRY -->"
README_CAPABILITIES_END = "<!-- END GENERATED CAPABILITY REGISTRY -->"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    LIMITED = "limited"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


class PublicStatus(StrEnum):
    """Roadmap truth-boundary vocabulary used by public product claims."""

    IMPLEMENTED = "Implemented"
    IMPLEMENTED_WITH_DISCLOSED_LIMITS = "Implemented with disclosed limits"
    PLANNED = "Planned"
    REJECTED = "Rejected"


@dataclass(frozen=True)
class Capability:
    """A production construct or explicitly disclosed production limitation."""

    id: str
    language: str
    construct: str
    status: SupportStatus
    description: str
    limitation: str
    benchmark_ids: tuple[str, ...] = ()
    benchmark_disclosure: str | None = None
    expected_diagnostic: str | None = None


@dataclass(frozen=True)
class PublicCapability:
    """One row in README's public capability assessment."""

    id: str
    name: str
    status: PublicStatus
    statement: str
    capability_ids: tuple[str, ...]


def _capability(
    id: str,
    language: str,
    construct: str,
    status: SupportStatus,
    description: str,
    limitation: str,
    *benchmark_ids: str,
    benchmark_disclosure: str | None = None,
    expected_diagnostic: str | None = None,
) -> Capability:
    return Capability(
        id=id,
        language=language,
        construct=construct,
        status=status,
        description=description,
        limitation=limitation,
        benchmark_ids=benchmark_ids,
        benchmark_disclosure=benchmark_disclosure,
        expected_diagnostic=expected_diagnostic,
    )


# This is the only hand-maintained construct/status declaration.  Keep entries
# sorted by stable id so registry serialization and all derived views are byte-
# stable.
CONSTRUCT_CAPABILITIES: tuple[Capability, ...] = (
    _capability(
        "python.class",
        "python",
        "class",
        SupportStatus.SUPPORTED,
        "Class definitions.",
        "Base-class semantics and metaclass behavior are not inferred.",
        "py.class.def",
    ),
    _capability(
        "python.decorator",
        "python",
        "decorator",
        SupportStatus.SUPPORTED,
        "Decorator observations and symbol properties.",
        "Only syntax-visible decorator names are recorded; runtime decorator semantics are not evaluated.",
        "py.decorator",
    ),
    _capability(
        "python.dynamic-import",
        "python",
        "dynamic-import",
        SupportStatus.UNSUPPORTED,
        "Dynamic imports.",
        "Dynamic import targets are not resolved.",
        "py.dynamic_import",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "python.function",
        "python",
        "function",
        SupportStatus.SUPPORTED,
        "Function definitions, including async and nested definitions.",
        "Signatures and runtime-generated functions are not modelled.",
        "py.function.def",
        "py.async_function.def",
        "py.nested_function",
        "py.duplicate_symbol",
    ),
    _capability(
        "python.http-client",
        "python",
        "http-client",
        SupportStatus.SUPPORTED,
        "Outbound HTTP call sites on requests/httpx attribute calls, including module aliases and client/session objects.",
        (
            "Only attribute-form calls on a module-level requests/httpx binding, or on a local name assigned directly "
            "from requests.Session()/httpx.Client()/httpx.AsyncClient(), are recognized. Both the method and an "
            "absolute literal URL must be syntax-visible; nothing is inferred from configuration, base URLs, or "
            "runtime values."
        ),
        "py.http_requests",
        "py.http_httpx",
        "py.http_session",
    ),
    _capability(
        "python.http-dynamic-destination",
        "python",
        "http-dynamic-destination",
        SupportStatus.UNSUPPORTED,
        "HTTP call sites whose method or destination is not a syntax-visible absolute literal.",
        "Computed URLs, f-strings, relative paths, computed methods, shadowed client names, and bare imported client functions produce a diagnostic and no destination fact.",
        "py.http_dynamic",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "python.import",
        "python",
        "import",
        SupportStatus.SUPPORTED,
        "Python import and from-import observations.",
        "Resolution is deliberately conservative and does not execute imports.",
        "py.import",
        "py.import_alias",
        "py.from_import",
    ),
    _capability(
        "python.metaclass",
        "python",
        "metaclass",
        SupportStatus.UNSUPPORTED,
        "Metaclass declarations.",
        "Metaclass runtime behavior is not modelled.",
        "py.metaclass",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "python.method",
        "python",
        "method",
        SupportStatus.SUPPORTED,
        "Methods defined inside classes.",
        "Dynamic attributes and runtime method replacement are not modelled.",
        "py.method.def",
    ),
    _capability(
        "python.module",
        "python",
        "module",
        SupportStatus.SUPPORTED,
        "Directory-scoped Python module nodes.",
        "Module identity is path-based.",
        "py.module",
    ),
    _capability(
        "python.monkeypatch",
        "python",
        "monkeypatch",
        SupportStatus.UNSUPPORTED,
        "Assignments that monkey-patch imported names.",
        "Imported-name rebinding is reported but not interpreted as a stable relationship.",
        "py.monkeypatch",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "python.reflection",
        "python",
        "reflection",
        SupportStatus.UNSUPPORTED,
        "Reflection calls such as getattr().",
        "Reflection targets are not resolved.",
        "py.reflection",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "python.route",
        "python",
        "route",
        SupportStatus.SUPPORTED,
        "Literal route paths on supported decorator forms.",
        "The route contract covers syntax-visible literal paths only.",
        "py.fastapi_route",
    ),
    _capability(
        "python.star-import",
        "python",
        "star-import",
        SupportStatus.UNSUPPORTED,
        "Wildcard imports.",
        "Star-import bindings are not expanded.",
        "py.star_import",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "source.binary-file",
        "source",
        "binary-file",
        SupportStatus.UNSUPPORTED,
        "NUL-containing source files.",
        "Binary files do not receive source line evidence.",
        "src.binary_file",
        expected_diagnostic="RI-SRC-BINARY",
    ),
    _capability(
        "source.empty-file",
        "source",
        "empty-file",
        SupportStatus.SUPPORTED,
        "Empty text files with one logical line.",
        "Empty files have whole-file evidence at logical line 1.",
        "src.empty_file",
    ),
    _capability(
        "source.file",
        "source",
        "file",
        SupportStatus.SUPPORTED,
        "Repository inventory file nodes.",
        "Inventory is not semantic extraction for unsupported languages.",
        "src.file",
    ),
    _capability(
        "source.large-file",
        "source",
        "large-file",
        SupportStatus.UNSUPPORTED,
        "Files above the configured source budget.",
        "Oversized source is skipped rather than retained for extraction.",
        "src.large_file",
        expected_diagnostic="RI-LIMIT-SKIP",
    ),
    _capability(
        "source.malformed-source",
        "source",
        "malformed-source",
        SupportStatus.UNSUPPORTED,
        "Undecodable or malformed source.",
        "Malformed input produces a diagnostic and no fabricated facts.",
        "py.syntax_error",
        "ts.syntax_error",
        "src.malformed_source",
        expected_diagnostic="RI-SRC-MALFORMED",
    ),
    _capability(
        "source.path-escape",
        "source",
        "path-escape",
        SupportStatus.UNSUPPORTED,
        "Paths that are absolute or escape the repository root.",
        "Unsafe paths are rejected before extraction.",
        "src.path_escape",
        expected_diagnostic="RI-SEC-PATH-ESCAPE",
    ),
    _capability(
        "source.repository",
        "source",
        "repository",
        SupportStatus.SUPPORTED,
        "The repository root inventory node.",
        "The node identifies the analyzed revision; it is not a source-language claim.",
        "src.repository",
    ),
    _capability(
        "source.trailing-newline",
        "source",
        "trailing-newline",
        SupportStatus.SUPPORTED,
        "Logical line accounting for trailing newlines.",
        "Line accounting follows the ri.v1 empty/trailing-newline rules.",
        "src.trailing_newline",
    ),
    _capability(
        "typescript.ambient-module",
        "typescript",
        "ambient-module",
        SupportStatus.UNSUPPORTED,
        "Ambient module declarations.",
        "Ambient module semantics are not extracted.",
        "ts.ambient_module",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "typescript.class",
        "typescript",
        "class",
        SupportStatus.SUPPORTED,
        "TypeScript class declarations.",
        "Type information and runtime inheritance are not inferred beyond emitted syntax facts.",
        "ts.class",
    ),
    _capability(
        "typescript.commonjs-require",
        "typescript",
        "commonjs-require",
        SupportStatus.UNSUPPORTED,
        "CommonJS require() calls.",
        "CommonJS binding semantics are not resolved by the TypeScript extractor.",
        "ts.commonjs_require",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "typescript.const",
        "typescript",
        "const",
        SupportStatus.SUPPORTED,
        "Top-level const bindings.",
        "Only the supported declaration shape is emitted.",
        "ts.const",
    ),
    _capability(
        "typescript.decorator",
        "typescript",
        "decorator",
        SupportStatus.UNSUPPORTED,
        "TypeScript decorators.",
        "Decorator runtime semantics are not extracted.",
        "ts.decorator",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "typescript.dynamic-import",
        "typescript",
        "dynamic-import",
        SupportStatus.UNSUPPORTED,
        "Dynamic import expressions.",
        "Dynamic import targets are not resolved.",
        "ts.dynamic_import",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "typescript.enum",
        "typescript",
        "enum",
        SupportStatus.SUPPORTED,
        "Enum declarations.",
        "Enum runtime expansion is not inferred.",
        "ts.enum",
    ),
    _capability(
        "typescript.export",
        "typescript",
        "export",
        SupportStatus.SUPPORTED,
        "Export observations.",
        "Exports are recorded syntactically without module execution.",
        "ts.export",
        "ts.reexport",
    ),
    _capability(
        "typescript.file",
        "typescript",
        "file",
        SupportStatus.SUPPORTED,
        "TypeScript file nodes.",
        "File nodes carry inventory and language facts; semantic extraction remains construct-specific.",
        "ts.module",
    ),
    _capability(
        "typescript.function",
        "typescript",
        "function",
        SupportStatus.SUPPORTED,
        "Function declarations, including async functions.",
        "Type inference and runtime-generated functions are not modelled.",
        "ts.function",
        "ts.async_function",
    ),
    _capability(
        "typescript.http-client",
        "typescript",
        "http-client",
        SupportStatus.SUPPORTED,
        "Outbound HTTP call sites on fetch and axios, including a default-import axios alias.",
        (
            "Only a global fetch() call or an attribute call on a module-level axios default import is recognized. "
            "The destination must be an absolute literal URL, and the method must be either fetch's specified GET "
            "default, a literal 'method' in an inline init object, or the axios method name."
        ),
        "ts.http_fetch",
        "ts.http_axios",
    ),
    _capability(
        "typescript.http-dynamic-destination",
        "typescript",
        "http-dynamic-destination",
        SupportStatus.UNSUPPORTED,
        "HTTP call sites whose method or destination is not a syntax-visible absolute literal.",
        "Template literals with substitutions, variable URLs, relative paths, computed init objects, and shadowed fetch/axios bindings produce a diagnostic and no destination fact.",
        "ts.http_dynamic",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "typescript.import",
        "typescript",
        "import",
        SupportStatus.SUPPORTED,
        "TypeScript import observations and bindings.",
        "Resolution is syntax- and snapshot-fact-based; source is not executed.",
        "ts.import",
        "ts.import_alias",
    ),
    _capability(
        "typescript.interface",
        "typescript",
        "interface",
        SupportStatus.SUPPORTED,
        "Interface declarations.",
        "Structural type checking is not performed.",
        "ts.interface",
    ),
    _capability(
        "typescript.method",
        "typescript",
        "method",
        SupportStatus.SUPPORTED,
        "Class methods.",
        "Dynamic dispatch and runtime replacement are not modelled.",
        "ts.method",
    ),
    _capability(
        "typescript.module",
        "typescript",
        "module",
        SupportStatus.SUPPORTED,
        "Directory-scoped TypeScript module nodes.",
        "Module identity is path-based.",
        "ts.directory_module",
    ),
    _capability(
        "typescript.namespace",
        "typescript",
        "namespace",
        SupportStatus.UNSUPPORTED,
        "Namespace/module declarations.",
        "Namespace runtime and merge semantics are not extracted.",
        "ts.namespace",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "typescript.route",
        "typescript",
        "route",
        SupportStatus.SUPPORTED,
        "Literal routes in supported react-router forms.",
        "Dynamic route paths and unrelated path-shaped objects are not treated as routes.",
        "ts.route",
    ),
    _capability(
        "typescript.type",
        "typescript",
        "type",
        SupportStatus.SUPPORTED,
        "Type alias declarations.",
        "Type evaluation is not performed.",
        "ts.type",
    ),
)


MANIFEST_CAPABILITIES: tuple[Capability, ...] = (
    _capability(
        "dependency.package-json",
        "source",
        "manifest:package.json",
        SupportStatus.SUPPORTED,
        "Direct npm declarations in package.json.",
        "Only direct declarations are extracted; lockfiles, transitive resolution, vulnerability scanning, and outdated-version scanning are not implemented.",
        benchmark_disclosure="No benchmark fixture currently exercises dependency-manifest extraction; production integration tests cover this extractor.",
    ),
    _capability(
        "dependency.pyproject",
        "source",
        "manifest:pyproject.toml",
        SupportStatus.SUPPORTED,
        "Direct PyPI declarations in pyproject.toml.",
        "Only supported project.dependencies declarations are extracted; transitive resolution and scanning are not implemented.",
        benchmark_disclosure="No benchmark fixture currently exercises dependency-manifest extraction; production integration tests cover this extractor.",
    ),
    _capability(
        "dependency.requirements",
        "source",
        "manifest:requirements.txt",
        SupportStatus.SUPPORTED,
        "Direct PyPI declarations in requirements.txt.",
        "Only direct requirement lines are extracted; transitive resolution and scanning are not implemented.",
        benchmark_disclosure="No benchmark fixture currently exercises dependency-manifest extraction; production integration tests cover this extractor.",
    ),
)


LOCKFILE_CAPABILITIES: tuple[Capability, ...] = (
    _capability(
        "lockfile.npm-package-lock",
        "source",
        "lockfile:package-lock.json",
        SupportStatus.SUPPORTED,
        "Resolved npm versions from package-lock.json lockfileVersion 2 and 3.",
        (
            "Only entries under a node_modules/ path with a concrete version string are read; workspace link entries "
            "are skipped. A resolution records that a version was installed, not that the repository depends on the "
            "package directly, so no transitive dependency graph or depends_on edge is derived from a lockfile alone. "
            "yarn.lock, pnpm-lock.yaml, and npm-shrinkwrap.json are not read."
        ),
        "src.npm_lockfile",
        "src.npm_lockfile_nested",
    ),
    _capability(
        "lockfile.npm-package-lock-v1",
        "source",
        "lockfile:package-lock.json@v1",
        SupportStatus.UNSUPPORTED,
        "package-lock.json lockfileVersion 1.",
        "Version 1 predates the packages table this extractor reads; it is disclosed rather than parsed from the legacy dependencies tree.",
        "src.npm_lockfile_v1",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
    _capability(
        "lockfile.poetry-lock",
        "source",
        "lockfile:poetry.lock",
        SupportStatus.SUPPORTED,
        "Resolved PyPI versions from poetry.lock with lock-version major 1 or 2.",
        (
            "Only each [[package]] table's name and version are read. Lock-version 2 removed the per-package category "
            "field, so the production/development split is reported as unknown rather than guessed. Pipfile.lock, "
            "uv.lock, and pdm.lock are not read."
        ),
        "src.poetry_lockfile",
    ),
)


IAC_CAPABILITIES: tuple[Capability, ...] = (
    _capability(
        "iac.docker-compose",
        "source",
        "iac:docker-compose",
        SupportStatus.SUPPORTED,
        "Declared services, volumes, and networks in Docker Compose manifests.",
        (
            "Only the four canonical Compose filenames are read, and only the services, volumes, and networks "
            "sections. Provenance is the resource's declaration line, not its whole block. Deployment topology, "
            "profiles, and the configs/secrets sections are not modelled, and Terraform, Kubernetes, Helm, "
            "CloudFormation, Pulumi, and Ansible are not read at all."
        ),
        "src.compose_service",
        "src.compose_volume",
        "src.compose_network",
    ),
    _capability(
        "iac.templated-value",
        "source",
        "iac:templated-value",
        SupportStatus.UNSUPPORTED,
        "Interpolated Compose values such as image: ${TAG}.",
        "A templated value is not an observed concrete value; the property is omitted and the blind spot is disclosed at the resource's span.",
        "src.compose_templated",
        expected_diagnostic="RI-EXT-UNSUPPORTED",
    ),
)


def _product_capability(
    id: str,
    status: SupportStatus,
    description: str,
    limitation: str,
) -> Capability:
    return _capability(
        f"product.{id}",
        "product",
        id,
        status,
        description,
        limitation,
        benchmark_disclosure=(
            "This product-level claim is verified by its focused integration or acceptance "
            "tests rather than the Repository Intelligence golden benchmark."
        ),
    )


PRODUCT_CAPABILITIES: tuple[Capability, ...] = (
    _product_capability(
        "ai-provider",
        SupportStatus.LIMITED,
        "AI provider integration.",
        "Provider answers receive bounded structural context and do not automatically carry source citations.",
    ),
    _product_capability(
        "analysis-lifecycle",
        SupportStatus.SUPPORTED,
        "Database-backed analysis lifecycle.",
        "Execution remains bounded by the configured worker and retry policy.",
    ),
    _product_capability(
        "architecture-authentication",
        SupportStatus.LIMITED,
        "Architecture and authentication explanation.",
        "Classification and authentication coverage are deliberately heuristic and pattern-bounded.",
    ),
    _product_capability(
        "archive-import",
        SupportStatus.SUPPORTED,
        "Archive upload and public GitHub import.",
        "Private GitHub cloning and non-GitHub repository hosts are not supported.",
    ),
    _product_capability(
        "async-processing",
        SupportStatus.PARTIAL,
        "Asynchronous analysis processing.",
        "Import, initial extraction, and file-tree parsing remain synchronous.",
    ),
    _product_capability(
        "authentication-isolation",
        SupportStatus.SUPPORTED,
        "Authentication and owner isolation.",
        "Protected resources deliberately conceal non-owner existence with 404 responses.",
    ),
    _product_capability(
        "change-impact",
        SupportStatus.LIMITED,
        "Change-impact traversal.",
        "Traversal covers one sealed snapshot and does not compare revisions.",
    ),
    _product_capability(
        "dependency-graph",
        SupportStatus.LIMITED,
        "Direct dependency graph with supported lockfile resolutions.",
        (
            "Declarations come from supported manifests and resolved pins from supported lockfiles only. A lockfile "
            "resolution never becomes a depends_on edge on its own, so transitive resolution is still not claimed, "
            "and vulnerability and outdated-version scanning are not implemented."
        ),
    ),
    _product_capability(
        "dependency-scanning",
        SupportStatus.NOT_ASSESSED,
        "Vulnerability and outdated-dependency scanning.",
        "This capability is planned; current responses explicitly publish not-computed or not-assessed states.",
    ),
    _product_capability(
        "documentation-export",
        SupportStatus.LIMITED,
        "Documentation and report export.",
        "Documentation uses current-revision structural facts.",
    ),
    _product_capability(
        "engineering-review",
        SupportStatus.LIMITED,
        "Evidence-addressed engineering review.",
        "No overall score, grade, health percentage, vulnerability result, or generated roadmap is produced.",
    ),
    _product_capability(
        "iac-resources",
        SupportStatus.LIMITED,
        "Infrastructure-as-code resource inventory.",
        "Only Docker Compose services, volumes, and networks are extracted; no other IaC format is read and no deployment behaviour is inferred.",
    ),
    _product_capability(
        "grounded-ai",
        SupportStatus.NOT_ASSESSED,
        "Grounded, cited free-form AI answers.",
        "This capability is planned; current provider answers intentionally remain uncited.",
    ),
    _product_capability(
        "repository-explorer",
        SupportStatus.SUPPORTED,
        "Owner-scoped repository explorer.",
        "Preview is bounded and binary-aware.",
    ),
    _product_capability(
        "repository-insights",
        SupportStatus.LIMITED,
        "Repository insights.",
        "Insights describe one snapshot and make no change-over-time claims.",
    ),
    _product_capability(
        "repository-intelligence",
        SupportStatus.LIMITED,
        "Revision-addressed Repository Intelligence snapshots.",
        "Semantic extraction is strongest for supported Python and TypeScript/JavaScript constructs.",
    ),
    _product_capability(
        "service-interactions",
        SupportStatus.LIMITED,
        "Outbound service-interaction discovery.",
        "Only syntax-proven absolute literal destinations on supported Python and TS/JS HTTP clients become edges; every other call site stays a diagnostic.",
    ),
    _product_capability(
        "revision-comparison",
        SupportStatus.NOT_ASSESSED,
        "Incremental re-analysis and revision comparison.",
        "This capability is planned; the current workflow re-analyses the full repository.",
    ),
)


def _supported_filenames(capabilities: tuple[Capability, ...], prefix: str) -> tuple[str, ...]:
    """Derive the accepted filename set from the registry's supported entries.

    Source selection must never drift from what the registry claims, so the
    extractors read their ``supports()`` filenames from here rather than keeping
    a second hand-maintained list. A construct id carrying a format qualifier
    (``lockfile:package-lock.json@v1``) contributes no filename of its own — it
    describes an unsupported revision of a filename already listed.
    """

    return tuple(
        sorted(
            {
                item.construct.removeprefix(prefix)
                for item in capabilities
                if item.status == SupportStatus.SUPPORTED and "@" not in item.construct
            }
        )
    )


_SUPPORTED_MANIFEST_FILENAMES = _supported_filenames(MANIFEST_CAPABILITIES, "manifest:")
_SUPPORTED_LOCKFILE_FILENAMES = _supported_filenames(LOCKFILE_CAPABILITIES, "lockfile:")

# Compose accepts four canonical filenames for one format, so the registry
# carries the format id and the filename set is spelled out beside it.
_SUPPORTED_IAC_FILENAMES: tuple[str, ...] = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
)


def _code_list(items: tuple[str, ...]) -> str:
    rendered = [f"`{item}`" for item in items]
    if len(rendered) == 1:
        return rendered[0]
    # Two items take a plain "a and b"; the serial comma only applies from three.
    if len(rendered) == 2:
        return f"{rendered[0]} and {rendered[1]}"
    return f"{', '.join(rendered[:-1])}, and {rendered[-1]}"


PUBLIC_CAPABILITIES: tuple[PublicCapability, ...] = (
    PublicCapability(
        "archive-import",
        "Archive upload and public GitHub import",
        PublicStatus.IMPLEMENTED,
        "ZIP/TAR-family archives and shallow public GitHub HTTPS clones; size and path-safety limits apply. Private GitHub cloning and other repository hosts are not supported.",
        ("product.archive-import",),
    ),
    PublicCapability(
        "repository-explorer",
        "Repository explorer",
        PublicStatus.IMPLEMENTED,
        "Owner-scoped file tree plus bounded text/image preview, binary detection, and truncation.",
        ("product.repository-explorer",),
    ),
    PublicCapability(
        "authentication-isolation",
        "Authentication and owner isolation",
        PublicStatus.IMPLEMENTED,
        "Email/password, Argon2, short-lived access tokens, rotating refresh tokens with reuse detection. Protected resources are owner-scoped; non-owner access returns 404.",
        ("product.authentication-isolation",),
    ),
    PublicCapability(
        "analysis-lifecycle",
        "Analysis lifecycle",
        PublicStatus.IMPLEMENTED,
        "Database-backed, cancellable job with progress, bounded retry, lease renewal, and stale-worker recovery.",
        ("product.analysis-lifecycle",),
    ),
    PublicCapability(
        "repository-intelligence",
        "Repository Intelligence",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Immutable, revision-addressed `ri.v1` snapshots with normalized facts, evidence, query APIs, and a total canonical graph hash. Semantic extraction is strongest for supported Python and TypeScript/JavaScript constructs.",
        ("product.repository-intelligence",),
    ),
    PublicCapability(
        "architecture-authentication",
        "Architecture and authentication explanation",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Interactive snapshot-backed graph. Module/layer classification is heuristic. The cited authentication subgraph covers supported Python/FastAPI patterns only.",
        ("product.architecture-authentication",),
    ),
    PublicCapability(
        "dependency-graph",
        "Dependency Graph",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        (
            f"Direct declarations from {_code_list(_SUPPORTED_MANIFEST_FILENAMES)} plus resolved pins from "
            f"{_code_list(_SUPPORTED_LOCKFILE_FILENAMES)}, merged onto one dependency identity with repeated "
            "workspace declarations and exact spans. A lockfile pin is recorded as a resolution, never as a direct "
            "dependency edge, so transitive resolution is still not claimed."
        ),
        (
            "product.dependency-graph",
            *(item.id for item in MANIFEST_CAPABILITIES),
            *(item.id for item in LOCKFILE_CAPABILITIES if item.status == SupportStatus.SUPPORTED),
        ),
    ),
    PublicCapability(
        "service-interactions",
        "Service-interaction discovery",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Outbound HTTP call sites on `requests`, `httpx`, `fetch`, and `axios` resolve to a service node identified by its absolute origin, with the literal method and path on the call's own observation. A computed, relative, or shadowed destination is a diagnostic, never an edge.",
        ("product.service-interactions", "python.http-client", "typescript.http-client"),
    ),
    PublicCapability(
        "iac-resources",
        "Infrastructure-as-code resources",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Declared Docker Compose services, volumes, and networks with their exact declaration spans. Templated values are disclosed rather than reported as observed, and no other IaC format is read.",
        ("product.iac-resources", "iac.docker-compose"),
    ),
    PublicCapability(
        "engineering-review",
        "Engineering Review",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "`engineering-review.v2`; evidence-addressed findings and explicit category states. No overall score, grade, health percentage, vulnerability result, or generated roadmap.",
        ("product.engineering-review",),
    ),
    PublicCapability(
        "repository-insights",
        "Repository Insights",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "`repository-insights.v1`; defined counts, ratios, diagnostics, language breakdowns, and extraction coverage from one snapshot. No change-over-time claims.",
        ("product.repository-insights",),
    ),
    PublicCapability(
        "documentation-export",
        "Documentation and report export",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Documentation uses current-revision structural facts. Review, Documentation, Architecture, and Dependencies export through one JSON/Markdown/HTML/PDF pipeline.",
        ("product.documentation-export",),
    ),
    PublicCapability(
        "ai-provider",
        "AI provider integration",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Per-user configuration for supported providers, encrypted API keys, and constrained outbound destinations. Free-form answers receive structural facts and observed paths\u2014not source bytes or line spans\u2014and return no automatic citations.",
        ("product.ai-provider",),
    ),
    PublicCapability(
        "async-processing",
        "Asynchronous processing",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Analysis runs off the request path. Import, extraction of the initial archive/clone, and file-tree parsing remain synchronous; one in-process worker handles analysis jobs.",
        ("product.async-processing",),
    ),
    PublicCapability(
        "revision-comparison",
        "Incremental re-analysis and revision comparison",
        PublicStatus.PLANNED,
        "The full repository is analysed again; no snapshot-to-snapshot product workflow is available.",
        ("product.revision-comparison",),
    ),
    PublicCapability(
        "change-impact",
        "Change-impact or blast-radius analysis",
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS,
        "Owner-scoped traversal over one sealed snapshot's resolved import and dependency edges. It does not compare revisions or calculate churn or trends.",
        ("product.change-impact",),
    ),
    PublicCapability(
        "dependency-scanning",
        "Vulnerability and outdated-dependency scanning",
        PublicStatus.PLANNED,
        "Dependency responses report explicit `not_computed` states; Review keeps vulnerability scanning `not_assessed`. No clean bill of health or zero count is fabricated.",
        ("product.dependency-scanning",),
    ),
    PublicCapability(
        "grounded-ai",
        "Grounded, cited free-form AI answers",
        PublicStatus.PLANNED,
        "Provider answers are intentionally uncited because providers do not receive source content or line numbers.",
        ("product.grounded-ai",),
    ),
)


CAPABILITY_REGISTRY: tuple[Capability, ...] = tuple(
    sorted(
        (
            *CONSTRUCT_CAPABILITIES,
            *IAC_CAPABILITIES,
            *LOCKFILE_CAPABILITIES,
            *MANIFEST_CAPABILITIES,
            *PRODUCT_CAPABILITIES,
        ),
        key=lambda item: item.id,
    )
)
CAPABILITIES_BY_ID = {item.id: item for item in CAPABILITY_REGISTRY}


@dataclass(frozen=True)
class LanguageSupport:
    """Compatibility projection consumed by existing extractor tests."""

    supported: tuple[str, ...]
    unsupported: tuple[str, ...]


def validate_registry(
    capabilities: Iterable[Capability] = CAPABILITY_REGISTRY,
    public_capabilities: Iterable[PublicCapability] = PUBLIC_CAPABILITIES,
) -> None:
    entries = tuple(capabilities)
    ids = [item.id for item in entries]
    if ids != sorted(ids):
        raise ValueError("capability registry entries must be ordered by stable id")
    if len(ids) != len(set(ids)):
        raise ValueError("capability registry contains duplicate capability ids")
    for item in entries:
        if not item.id or not item.language or not item.construct:
            raise ValueError(f"capability {item.id!r} is missing a stable identity")
        if not isinstance(item.status, SupportStatus):
            raise ValueError(f"capability {item.id!r} has an unsupported status")
        if not item.description or not item.limitation:
            raise ValueError(f"capability {item.id!r} must disclose description and limitation")
        if item.status == SupportStatus.UNSUPPORTED and not item.expected_diagnostic:
            raise ValueError(f"unsupported capability {item.id!r} must name its diagnostic")
        if item.status != SupportStatus.UNSUPPORTED and item.expected_diagnostic:
            raise ValueError(f"supported capability {item.id!r} cannot require an unsupported diagnostic")
        if not item.benchmark_ids and not item.benchmark_disclosure:
            raise ValueError(f"capability {item.id!r} needs benchmark coverage or an explicit disclosure")
        if len(item.benchmark_ids) != len(set(item.benchmark_ids)):
            raise ValueError(f"capability {item.id!r} contains duplicate benchmark ids")

    capabilities_by_id = {item.id: item for item in entries}
    allowed_statuses = {
        PublicStatus.IMPLEMENTED: {SupportStatus.SUPPORTED},
        PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS: {
            SupportStatus.SUPPORTED,
            SupportStatus.LIMITED,
            SupportStatus.PARTIAL,
        },
        PublicStatus.PLANNED: {SupportStatus.NOT_ASSESSED},
        PublicStatus.REJECTED: {SupportStatus.UNSUPPORTED},
    }
    for public in public_capabilities:
        if not isinstance(public.status, PublicStatus):
            raise ValueError(f"public capability {public.id!r} has an unsupported status")
        if not public.capability_ids:
            raise ValueError(f"public capability {public.id!r} must resolve to registry capabilities")
        resolved = []
        for capability_id in public.capability_ids:
            capability = capabilities_by_id.get(capability_id)
            if capability is None:
                raise ValueError(f"public capability {public.id!r} references unknown capability {capability_id!r}")
            resolved.append(capability)
        if any(item.status not in allowed_statuses[public.status] for item in resolved):
            raise ValueError(f"public capability {public.id!r} status is inconsistent with its registry capabilities")
        if public.status == PublicStatus.IMPLEMENTED_WITH_DISCLOSED_LIMITS and not any(
            item.status in {SupportStatus.LIMITED, SupportStatus.PARTIAL} for item in resolved
        ):
            raise ValueError(f"public capability {public.id!r} must resolve to a disclosed limited capability")


# Deliberate fail-fast: registry drift is an application-startup error because
# extractors and public claims must never run from an invalid truth contract.
validate_registry()

# The compatibility view covers language constructs only. Manifest-family
# capabilities (manifest, lockfile, IaC) are keyed by filename or format rather
# than by a syntax construct, so they are projected out here and consumed
# through their own filename accessors.
_MATRIX_EXCLUDED_PREFIXES = ("iac:", "lockfile:", "manifest:")
_MATRIX_CAPABILITIES = tuple(
    item
    for item in CAPABILITY_REGISTRY
    if item.language in {"python", "source", "typescript"} and not item.construct.startswith(_MATRIX_EXCLUDED_PREFIXES)
)
SUPPORT_MATRIX: dict[str, LanguageSupport] = {
    language: LanguageSupport(
        supported=tuple(
            item.construct
            for item in _MATRIX_CAPABILITIES
            if item.language == language and item.status == SupportStatus.SUPPORTED
        ),
        unsupported=tuple(
            item.construct
            for item in _MATRIX_CAPABILITIES
            if item.language == language and item.status == SupportStatus.UNSUPPORTED
        ),
    )
    for language in sorted({item.language for item in _MATRIX_CAPABILITIES})
}


def supported_manifest_filenames() -> tuple[str, ...]:
    return _SUPPORTED_MANIFEST_FILENAMES


def supported_lockfile_filenames() -> tuple[str, ...]:
    return _SUPPORTED_LOCKFILE_FILENAMES


def supported_iac_filenames() -> tuple[str, ...]:
    return _SUPPORTED_IAC_FILENAMES


def render_readme_capabilities() -> str:
    lines = [
        README_CAPABILITIES_START,
        "| Capability | Status | Current boundary |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item.name} | **{item.status}** | {item.statement} |" for item in PUBLIC_CAPABILITIES)
    lines.extend(
        [
            "",
            "**Implemented with disclosed limits** means the workflow exists with an explicit coverage or trust boundary. **Planned** means it is roadmap work and current responses do not manufacture an answer. **Rejected** means the capability is intentionally outside the product contract.",
            README_CAPABILITIES_END,
        ]
    )
    return "\n".join(lines)


def check_readme_capabilities(readme: Path) -> None:
    content = readme.read_text(encoding="utf-8")
    start = content.find(README_CAPABILITIES_START)
    end = content.find(README_CAPABILITIES_END)
    if start < 0 or end < start:
        raise ValueError("README is missing the generated capability registry markers")
    actual = content[start : end + len(README_CAPABILITIES_END)]
    expected = render_readme_capabilities()
    if actual != expected:
        raise ValueError("README capability registry block is stale; run the reviewed registry renderer")
