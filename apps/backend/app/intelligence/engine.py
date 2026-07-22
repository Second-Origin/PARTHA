from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.intelligence.models import (
    EnvironmentFileEvidence,
    DependencyDeclaration,
    DependencyDiagnostic,
    KnowledgeGraph,
    KnowledgeGraphNode,
    KnowledgeGraphRelationship,
    RepositoryDependency,
    RepositoryDiscovery,
    RepositoryIntelligence,
    RepositoryModule,
    RepositoryStatistics,
    SourceFileIntelligence,
    SourceRole,
    SourceSymbol,
)
from app.intelligence import canonical
from app.models.repository import RepositoryRecord
from app.schemas.repository import FileTreeNode, RepositoryMeta

SOURCE_EXTENSIONS = {"py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "kt", "swift", "cs"}
DOC_EXTENSIONS = {"md", "mdx", "rst"}
CONFIG_NAMES = {
    "package.json",
    "tsconfig.json",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    ".env.example",
    ".gitignore",
    "alembic.ini",
}
ENVIRONMENT_TEMPLATE_NAMES = {".env.example", ".env.sample", ".env.template", ".env.dist"}
SECRET_KEY_NAME_PATTERN = re.compile(
    r"(?:^|_)(?:api_?key|access_?key(?:_?id)?|auth_?token|client_?secret|"
    r"credentials?|passw(?:or)?d|pwd|private_?key|secret_?key|secret|token)$",
    flags=re.IGNORECASE,
)
PLACEHOLDER_VALUE_PATTERN = re.compile(
    r"^(?:\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*|<[^>]+>|\[[^]]+\]|(?:example|sample|placeholder|replace|your)[\s_-].*|(?:change|replace)[\s_-]?me|not[\s_-]?a[\s_-]?real[\s_-]?.*|x+|\*+)$",
    flags=re.IGNORECASE,
)
NUMBER_VALUE_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[+-]?\d+)?", flags=re.IGNORECASE)
PATH_VALUE_PATTERN = re.compile(r"^(?:[A-Za-z]:[\\/]|[/~]|\.{1,2}[\\/]|file://)", flags=re.IGNORECASE)
URL_VALUE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
DATABASE_TECHNOLOGIES = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psycopg": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "sqlalchemy": "SQLAlchemy",
    "prisma": "Prisma",
}
CLOUD_TECHNOLOGIES = {
    "aws": "AWS",
    "boto3": "AWS",
    "azure": "Azure",
    "google-cloud": "Google Cloud",
    "gcp": "Google Cloud",
    "vercel": "Vercel",
    "netlify": "Netlify",
    "render": "Render",
    "railway": "Railway",
}


class RepositoryIntelligenceEngine:
    """Builds reusable repository intelligence from repository files.

    Extraction here is regex over file text and carries no line provenance. The
    evidence-backed extractors in ``app.extraction`` supersede it for TypeScript
    and Python; wiring those into this build path is #93.
    """

    def from_record(
        self,
        record: RepositoryRecord,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> RepositoryIntelligence:
        self._check_cancelled(check_cancelled)
        existing = self.load(record)
        if existing:
            if existing.discovery.environment_files and not existing.discovery.environment_file_evidence:
                # Legacy cache entries predate content-derived environment evidence. Upgrade
                # them in bounded O(environment files) time without rereading or rebuilding
                # the repository. Unknown legacy content is deliberately treated as a runtime
                # file, which cannot produce a critical secret-exposure finding.
                evidence: list[EnvironmentFileEvidence] = []
                for path in existing.discovery.environment_files:
                    self._check_cancelled(check_cancelled)
                    evidence.append(
                        EnvironmentFileEvidence(
                            path=path,
                            evidence_class="runtime_env_file_present",
                        )
                    )
                discovery = existing.discovery.model_copy(update={"environment_file_evidence": evidence})
                return existing.model_copy(update={"discovery": discovery})
            return existing
        tree: list[FileTreeNode] = []
        for node in record.file_tree or []:
            self._check_cancelled(check_cancelled)
            tree.append(FileTreeNode.model_validate(node))
        return self.build(
            repository_id=record.id,
            repository_name=record.name,
            root=Path(record.local_path),
            tree=tree,
            metadata=RepositoryMeta.model_validate(record.repo_metadata or {}),
            total_size=record.size,
            check_cancelled=check_cancelled,
        )

    def load(self, record: RepositoryRecord) -> RepositoryIntelligence | None:
        intelligence = (record.repo_metadata or {}).get("intelligence")
        if not intelligence:
            return None
        try:
            return RepositoryIntelligence.model_validate(intelligence)
        except ValueError:
            return None

    def persist(self, record: RepositoryRecord, intelligence: RepositoryIntelligence) -> None:
        metadata = dict(record.repo_metadata or {})
        metadata["intelligence"] = intelligence.model_dump(mode="json", by_alias=True)
        record.repo_metadata = metadata

    def build(
        self,
        repository_id: str,
        repository_name: str,
        root: Path,
        tree: list[FileTreeNode],
        metadata: RepositoryMeta,
        total_size: int,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> RepositoryIntelligence:
        self._check_cancelled(check_cancelled)
        flat_files = self._flatten_files(tree, check_cancelled=check_cancelled)
        file_intelligence: list[SourceFileIntelligence] = []
        for node in flat_files:
            self._check_cancelled(check_cancelled)
            file_intelligence.append(self._file_intelligence(root, node))
        symbols: list[SourceSymbol] = []
        for file in file_intelligence:
            self._check_cancelled(check_cancelled)
            symbols.extend(file.symbols)
        dependencies, dependency_manifest_count, dependency_diagnostics = self._dependencies(
            root,
            flat_files,
            check_cancelled=check_cancelled,
        )
        discovery = self._discovery(
            root,
            metadata,
            tree,
            file_intelligence,
            dependencies,
            total_size,
            check_cancelled=check_cancelled,
        )
        modules = self._modules(file_intelligence, check_cancelled=check_cancelled)
        graph = self._knowledge_graph(
            repository_id,
            repository_name,
            modules,
            file_intelligence,
            symbols,
            dependencies,
            check_cancelled=check_cancelled,
        )
        return RepositoryIntelligence(
            repository_id=repository_id,
            repository_name=repository_name,
            generated_at=datetime.now(UTC),
            metadata=metadata,
            discovery=discovery,
            modules=modules,
            files=file_intelligence,
            symbols=symbols,
            dependencies=dependencies,
            dependency_manifest_count=dependency_manifest_count,
            dependency_diagnostics=dependency_diagnostics,
            graph=graph,
        )

    def _flatten_files(
        self,
        nodes: list[FileTreeNode],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> list[FileTreeNode]:
        result: list[FileTreeNode] = []
        for node in nodes:
            self._check_cancelled(check_cancelled)
            if node.type == "file":
                result.append(node)
            if node.children:
                result.extend(
                    self._flatten_files(
                        node.children,
                        check_cancelled=check_cancelled,
                    )
                )
        return result

    @staticmethod
    def _check_cancelled(check_cancelled: Callable[[], None] | None) -> None:
        if check_cancelled is not None:
            check_cancelled()

    def _file_intelligence(self, root: Path, node: FileTreeNode) -> SourceFileIntelligence:
        path = node.path
        extension = node.extension
        language = node.language
        text = self._read_text(root, path)
        role = self._role(path, extension)
        imports = self._imports(text, extension)
        exports = self._exports(text, extension)
        api_routes = self._api_routes(text, extension)
        symbols = self._symbols(path, text, extension, exports, api_routes)
        technologies = self._technologies(path, text)
        return SourceFileIntelligence(
            path=path,
            name=node.name,
            module_id=self._module_id(path, role),
            language=language,
            extension=extension,
            size=node.size or 0,
            role=role,
            imports=imports,
            exports=exports,
            api_routes=api_routes,
            symbols=symbols,
            technologies=technologies,
        )

    def _read_text(self, root: Path, path: str) -> str:
        absolute = root / path.lstrip("/")
        if not absolute.exists() or absolute.stat().st_size > 512_000:
            return ""
        try:
            return absolute.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _role(self, path: str, extension: str | None) -> SourceRole:
        lowered = path.lower()
        name = lowered.rsplit("/", 1)[-1]
        if name.startswith("readme") or extension in DOC_EXTENSIONS:
            return "documentation"
        if name in {item.lower() for item in CONFIG_NAMES} or "/.github/" in lowered:
            return "configuration"
        if any(token in lowered for token in ["test", "spec", "__tests__"]):
            return "test"
        if name in {"main.py", "app.py", "main.ts", "main.tsx", "index.js", "index.ts"}:
            return "entrypoint"
        if "/controllers/" in lowered or "controller" in name:
            return "controller"
        if "/routes/" in lowered or "/api/" in lowered or "route" in name:
            return "route"
        if "/services/" in lowered or "service" in name:
            return "service"
        if "/repositories/" in lowered or "repository" in name or "repo" in name:
            return "repository"
        if "/models/" in lowered or "/schemas/" in lowered or "model" in name:
            return "model"
        if "dto" in name:
            return "dto"
        if "interface" in name:
            return "interface"
        if "enum" in name:
            return "enum"
        if "/utils/" in lowered or "/lib/" in lowered or "util" in name:
            return "utility"
        return "unknown"

    def _imports(self, text: str, extension: str | None) -> list[str]:
        imports: list[str] = []
        if extension in {"ts", "tsx", "js", "jsx"}:
            patterns = [
                r"import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]",
                r"export\s+.+?\s+from\s+['\"]([^'\"]+)['\"]",
                r"require\(['\"]([^'\"]+)['\"]\)",
            ]
            for pattern in patterns:
                imports.extend(re.findall(pattern, text))
        if extension == "py":
            imports.extend(re.findall(r"^\s*from\s+([\w.]+)\s+import\s+", text, flags=re.MULTILINE))
            imports.extend(re.findall(r"^\s*import\s+([\w.]+)", text, flags=re.MULTILINE))
        return sorted(set(imports))

    def _exports(self, text: str, extension: str | None) -> list[str]:
        exports: list[str] = []
        if extension in {"ts", "tsx", "js", "jsx"}:
            exports.extend(re.findall(r"export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)", text))
            exports.extend(re.findall(r"export\s+(?:default\s+)?class\s+(\w+)", text))
            exports.extend(re.findall(r"export\s+(?:interface|type|enum)\s+(\w+)", text))
            exports.extend(re.findall(r"export\s+const\s+(\w+)", text))
        if extension == "py":
            exports.extend(re.findall(r"^class\s+(\w+)", text, flags=re.MULTILINE))
            exports.extend(re.findall(r"^def\s+(\w+)", text, flags=re.MULTILINE))
        return sorted(set(exports))

    def _api_routes(self, text: str, extension: str | None) -> list[str]:
        routes: list[str] = []
        if extension == "py":
            routes.extend(re.findall(r"@(?:\w+\.)?(?:get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]", text))
        if extension in {"ts", "tsx", "js", "jsx"}:
            routes.extend(re.findall(r"\.(?:get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]", text))
        return sorted(set(routes))

    def _symbols(self, path: str, text: str, extension: str | None, exports: list[str], routes: list[str]) -> list[SourceSymbol]:
        symbols: list[SourceSymbol] = []
        patterns: list[tuple[str, str]] = []
        if extension in {"ts", "tsx", "js", "jsx"}:
            patterns = [
                ("function", r"(?:export\s+)?(?:async\s+)?function\s+(\w+)"),
                ("class", r"(?:export\s+)?class\s+(\w+)"),
                ("interface", r"(?:export\s+)?interface\s+(\w+)"),
                ("type", r"(?:export\s+)?type\s+(\w+)"),
                ("enum", r"(?:export\s+)?enum\s+(\w+)"),
                ("constant", r"(?:export\s+)?const\s+(\w+)"),
            ]
        elif extension == "py":
            patterns = [("class", r"^class\s+(\w+)"), ("function", r"^def\s+(\w+)")]

        for kind, pattern in patterns:
            for name in re.findall(pattern, text, flags=re.MULTILINE):
                symbols.append(
                    SourceSymbol(
                        id=self._symbol_id(path, name),
                        name=name,
                        kind=kind,  # type: ignore[arg-type]
                        file_path=path,
                        exported=name in exports or extension == "py",
                    )
                )
        for route in routes:
            symbols.append(SourceSymbol(id=self._symbol_id(path, route), name=route, kind="route", file_path=path, exported=True))
        return symbols

    def _technologies(self, path: str, text: str) -> list[str]:
        lowered = f"{path}\n{text}".lower()
        technologies: set[str] = set()
        for token, name in {**DATABASE_TECHNOLOGIES, **CLOUD_TECHNOLOGIES}.items():
            if token in lowered:
                technologies.add(name)
        if "dockerfile" in lowered or "docker-compose" in lowered:
            technologies.add("Docker")
        if "github/workflows" in lowered:
            technologies.add("GitHub Actions")
        return sorted(technologies)

    def _dependencies(
        self,
        root: Path,
        files: list[FileTreeNode],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> tuple[list[RepositoryDependency], int, list[DependencyDiagnostic]]:
        """Extract declarations from parser-approved manifest inventory only.

        ``RepositoryParser`` has already applied the repository's ignored-path
        policy to ``files``.  This bridge deliberately never walks ``root`` or
        guesses manifest locations; it forwards the selected bytes to the
        canonical manifest extractor and retains all returned provenance.
        """

        # Extraction modules import canonical path helpers from this package,
        # so load them only after the intelligence package has initialized.
        from app.extraction.manifests import DependencyManifestExtractor
        from app.extraction.pipeline import ExtractionPipeline

        extractor = DependencyManifestExtractor()
        pipeline = ExtractionPipeline((extractor,))
        manifest_count = 0
        diagnostics: list[DependencyDiagnostic] = []
        declarations_by_key: dict[str, list[DependencyDeclaration]] = defaultdict(list)
        for file in sorted(files, key=lambda item: item.path):
            self._check_cancelled(check_cancelled)
            try:
                path = canonical.normalize_repo_path(file.path.lstrip("/"))
            except canonical.PathEscapeError:
                continue
            if not extractor.supports(path):
                continue
            manifest_count += 1
            source_path = root / path
            try:
                reported_bytes = source_path.stat().st_size
            except OSError:
                # The parser inventory is the source of truth. A file that
                # disappears between inventory and analysis cannot become a
                # fabricated zero-dependency success state.
                diagnostics.append(
                    DependencyDiagnostic(
                        code="RI-SRC-MALFORMED",
                        category="malformed source",
                        severity="error",
                        message="dependency manifest could not be read from the parser-approved inventory",
                        path=path,
                        producer=extractor.producer,
                    )
                )
                continue
            if reported_bytes > pipeline.max_source_bytes:
                diagnostics.append(
                    DependencyDiagnostic(
                        code="RI-LIMIT-SKIP",
                        category="resource-limit skip",
                        severity="info",
                        message="file exceeds the configured source-size budget",
                        path=path,
                        producer=f"{pipeline.inventory_name}@{pipeline.inventory_version}",
                        details={
                            "budgetBytes": pipeline.max_source_bytes,
                            "reportedBytes": reported_bytes,
                        },
                    )
                )
                continue
            try:
                # Read at most one byte past the configured budget. This is a
                # second guard against a file growing after ``stat()`` and keeps
                # each candidate bounded rather than retaining all manifests.
                with source_path.open("rb") as source_file:
                    source = source_file.read(pipeline.max_source_bytes + 1)
            except OSError:
                diagnostics.append(
                    DependencyDiagnostic(
                        code="RI-SRC-MALFORMED",
                        category="malformed source",
                        severity="error",
                        message="dependency manifest could not be read from the parser-approved inventory",
                        path=path,
                        producer=extractor.producer,
                    )
                )
                continue
            if len(source) > pipeline.max_source_bytes:
                diagnostics.append(
                    DependencyDiagnostic(
                        code="RI-LIMIT-SKIP",
                        category="resource-limit skip",
                        severity="info",
                        message="file exceeds the configured source-size budget",
                        path=path,
                        producer=f"{pipeline.inventory_name}@{pipeline.inventory_version}",
                        details={
                            "budgetBytes": pipeline.max_source_bytes,
                            "reportedBytes": len(source),
                        },
                    )
                )
                continue

            for run in pipeline.run({path: source}, check_cancelled=check_cancelled):
                self._check_cancelled(check_cancelled)
                for diagnostic in run.result.diagnostics:
                    diagnostics.append(
                        DependencyDiagnostic(
                            code=diagnostic.code,
                            category=diagnostic.category,
                            severity=diagnostic.severity,
                            message=diagnostic.message,
                            path=diagnostic.path,
                            producer=run.producer,
                            details=dict(diagnostic.details) if diagnostic.details is not None else None,
                        )
                    )
                if run.producer != extractor.producer:
                    continue
                for node in run.result.nodes:
                    if node.node_kind != "dependency" or node.properties is None or not node.evidence:
                        continue
                    properties = node.properties
                    evidence = node.evidence[0]
                    ecosystem = str(properties["ecosystem"])
                    version = properties.get("version")
                    declaration = DependencyDeclaration(
                        name=node.name or node.stable_key.rsplit(":", 1)[-1],
                        manifest_path=str(properties["manifest_path"]),
                        workspace_path=str(properties["workspace_path"]),
                        start_line=evidence.start_line,
                        end_line=evidence.end_line,
                        extractor=run.producer_name,
                        extractor_version=run.producer_version,
                        ecosystem=ecosystem,
                        version=str(version) if version is not None else None,
                        type=properties["dependency_type"],  # type: ignore[arg-type]
                    )
                    declarations_by_key[node.stable_key].append(declaration)

        dependencies: list[RepositoryDependency] = []
        for stable_key, declarations in sorted(declarations_by_key.items()):
            self._check_cancelled(check_cancelled)
            ordered = sorted(
                declarations,
                key=lambda item: (
                    item.manifest_path,
                    item.start_line,
                    item.end_line,
                    item.type,
                    item.version or "",
                ),
            )
            first = ordered[0]
            versions = {declaration.version for declaration in ordered}
            types = {declaration.type for declaration in ordered}
            dependencies.append(
                RepositoryDependency(
                    id=f"dependency:{stable_key.removeprefix('dep:')}",
                    name=first.name,
                    version=next(iter(versions)) if len(versions) == 1 else None,
                    type=next(iter(types)) if len(types) == 1 else "multiple",
                    ecosystem=first.ecosystem,
                    source_file=first.manifest_path,
                    declarations=ordered,
                )
            )
        return (
            sorted(dependencies, key=lambda dependency: (dependency.ecosystem, dependency.name.lower(), dependency.id)),
            manifest_count,
            sorted(
                diagnostics,
                key=lambda diagnostic: (
                    diagnostic.path or "",
                    diagnostic.code,
                    diagnostic.producer,
                    diagnostic.message,
                ),
            ),
        )

    def _discovery(
        self,
        root: Path,
        metadata: RepositoryMeta,
        tree: list[FileTreeNode],
        files: list[SourceFileIntelligence],
        dependencies: list[RepositoryDependency],
        total_size: int,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> RepositoryDiscovery:
        self._check_cancelled(check_cancelled)
        language_counts = Counter(file.language for file in files if file.language)
        folders = self._count_folders(tree, check_cancelled=check_cancelled)
        paths = [file.path for file in files]
        dep_names = {dependency.name.lower() for dependency in dependencies}
        frameworks = sorted({metadata.framework, *self._frameworks_from_dependencies(dep_names)} - {"Unknown", ""})
        package_managers = sorted({metadata.package_manager} - {None})  # type: ignore[arg-type]
        config_files = [path.lstrip("/") for path in paths if Path(path).name in CONFIG_NAMES or "/.github/" in path]
        env_files = [path.lstrip("/") for path in paths if Path(path).name.startswith(".env")]
        environment_file_evidence = self._environment_file_evidence(
            root,
            env_files,
            check_cancelled=check_cancelled,
        )
        docker_files = [path.lstrip("/") for path in paths if "docker" in path.lower()]
        ci_files = [path.lstrip("/") for path in paths if "/.github/workflows/" in path or "gitlab-ci" in path.lower()]
        build_systems = self._build_systems(paths, dep_names)
        technologies = {technology for file in files for technology in file.technologies}
        database_technologies = sorted(technologies.intersection(set(DATABASE_TECHNOLOGIES.values())))
        cloud_providers = sorted(technologies.intersection(set(CLOUD_TECHNOLOGIES.values())))
        return RepositoryDiscovery(
            primary_language=metadata.language,
            languages=dict(language_counts),
            frameworks=frameworks,
            package_managers=package_managers,
            configuration_files=config_files,
            environment_files=env_files,
            environment_file_evidence=environment_file_evidence,
            docker_files=docker_files,
            ci_files=ci_files,
            entry_points=[metadata.entry_point] if metadata.entry_point else [],
            build_systems=build_systems,
            database_technologies=database_technologies,
            cloud_providers=cloud_providers,
            statistics=RepositoryStatistics(
                total_files=metadata.total_files,
                total_folders=folders,
                total_size=total_size,
                source_files=len([file for file in files if file.extension in SOURCE_EXTENSIONS]),
                test_files=len([file for file in files if file.role == "test"]),
                config_files=len(config_files),
                documentation_files=len([file for file in files if file.role == "documentation"]),
            ),
        )

    def _environment_file_evidence(
        self,
        root: Path,
        paths: list[str],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> list[EnvironmentFileEvidence]:
        evidence: list[EnvironmentFileEvidence] = []
        for path in paths:
            self._check_cancelled(check_cancelled)
            secret_keys = self._secret_like_keys(self._read_text(root, path))
            if secret_keys:
                evidence_class = "secret_like_value_detected"
            elif Path(path).name.lower() in ENVIRONMENT_TEMPLATE_NAMES:
                evidence_class = "template_present"
            else:
                evidence_class = "runtime_env_file_present"
            evidence.append(EnvironmentFileEvidence(path=path, evidence_class=evidence_class, secret_keys=secret_keys))
        return evidence

    def _secret_like_keys(self, text: str) -> list[str]:
        keys: set[str] = set()
        for line in text.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            if clean.startswith("export "):
                clean = clean.removeprefix("export ").lstrip()
            if "=" not in clean:
                continue
            key, value = clean.split("=", 1)
            key = key.strip()
            value = self._parse_dotenv_value(value)
            if not key or self._is_placeholder_value(value):
                continue
            if self._has_embedded_credentials(value) or (
                SECRET_KEY_NAME_PATTERN.search(key) and self._is_credible_secret_value(value)
            ):
                keys.add(key)
        return sorted(keys)

    def _parse_dotenv_value(self, value: str) -> str:
        """Remove dotenv quoting and an unquoted, whitespace-delimited comment."""
        normalized = value.strip()
        quote: str | None = None
        escaped = False
        for index, character in enumerate(normalized):
            if escaped:
                escaped = False
                continue
            if quote:
                if character == "\\" and quote == '"':
                    escaped = True
                elif character == quote:
                    quote = None
                continue
            if character in {'"', "'"}:
                quote = character
            elif character == "#" and (index == 0 or normalized[index - 1].isspace()):
                normalized = normalized[:index].rstrip()
                break
        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
            normalized = normalized[1:-1]
        return normalized

    def _is_placeholder_value(self, value: str) -> bool:
        normalized = value.strip()
        if not normalized or normalized.lower() in {
            "none",
            "null",
            "undefined",
            "example",
            "sample",
            "placeholder",
            "replace",
            "your",
            "user",
            "username",
            "password",
            "pass",
            "pwd",
            "secret",
            "token",
        }:
            return True
        return bool(PLACEHOLDER_VALUE_PATTERN.fullmatch(normalized))

    def _is_credible_secret_value(self, value: str) -> bool:
        """Require value-shaped evidence in addition to a sensitive key name."""
        normalized = value.strip()
        if self._is_placeholder_value(normalized):
            return False
        if normalized.lower() in {"true", "false", "yes", "no", "on", "off", "enabled", "disabled"}:
            return False
        if NUMBER_VALUE_PATTERN.fullmatch(normalized):
            return False
        if PATH_VALUE_PATTERN.match(normalized):
            return False
        if URL_VALUE_PATTERN.match(normalized):
            return self._has_embedded_credentials(normalized)
        if len(normalized) < 8:
            return False
        character_classes = sum(
            (
                any(character.islower() for character in normalized),
                any(character.isupper() for character in normalized),
                any(character.isdigit() for character in normalized),
                any(not character.isalnum() for character in normalized),
            )
        )
        return character_classes >= 2 or len(normalized) >= 16

    def _has_embedded_credentials(self, value: str) -> bool:
        if "-----BEGIN" in value and "PRIVATE KEY-----" in value:
            return True
        # A URL userinfo section only counts as an exposed credential when the
        # password is a concrete value, not a placeholder or a ${VAR} reference
        # (e.g. postgres://user:password@host and postgres://user:${PW}@host are
        # template idioms, not committed secrets).
        userinfo = re.search(r"://[^/@\s]+:([^/@\s]+)@", value)
        return bool(userinfo) and not self._is_placeholder_value(userinfo.group(1))

    def _count_folders(
        self,
        nodes: list[FileTreeNode],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> int:
        count = 0
        for node in nodes:
            self._check_cancelled(check_cancelled)
            if node.type == "folder":
                count += 1
            if node.children:
                count += self._count_folders(
                    node.children,
                    check_cancelled=check_cancelled,
                )
        return count

    def _frameworks_from_dependencies(self, dep_names: set[str]) -> set[str]:
        frameworks: set[str] = set()
        mapping = {"react": "React", "next": "Next.js", "vue": "Vue", "fastapi": "FastAPI", "django": "Django", "flask": "Flask"}
        for dependency, framework in mapping.items():
            if dependency in dep_names:
                frameworks.add(framework)
        return frameworks

    def _build_systems(self, paths: list[str], dep_names: set[str]) -> list[str]:
        systems: set[str] = set()
        names = {Path(path).name for path in paths}
        if "package.json" in names:
            systems.add("npm")
        if "vite.config.ts" in names or "vite" in dep_names:
            systems.add("Vite")
        if "next" in dep_names:
            systems.add("Next.js")
        if "pyproject.toml" in names:
            systems.add("pyproject")
        if "requirements.txt" in names:
            systems.add("pip")
        if "Dockerfile" in names or "docker-compose.yml" in names:
            systems.add("Docker")
        return sorted(systems)

    def _modules(
        self,
        files: list[SourceFileIntelligence],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> list[RepositoryModule]:
        grouped: dict[str, list[SourceFileIntelligence]] = defaultdict(list)
        for file in files:
            self._check_cancelled(check_cancelled)
            grouped[file.module_id].append(file)
        modules: list[RepositoryModule] = []
        for module_id, module_files in grouped.items():
            self._check_cancelled(check_cancelled)
            role = self._dominant_role(module_files)
            dependencies = sorted({import_name for file in module_files for import_name in file.imports})
            symbols = sorted({symbol.id for file in module_files for symbol in file.symbols})
            modules.append(
                RepositoryModule(
                    id=module_id,
                    name=module_id.replace("module:", "").replace("-", " ").title(),
                    role=role,
                    layer=self._layer(role),
                    path_prefix=self._path_prefix(module_files),
                    files=[file.path for file in module_files],
                    symbols=symbols,
                    dependencies=dependencies,
                )
            )
        return sorted(modules, key=lambda module: module.id)

    def _dominant_role(self, files: list[SourceFileIntelligence]) -> SourceRole:
        roles = [file.role for file in files if file.role not in {"unknown", "documentation", "test"}]
        if not roles:
            return files[0].role if files else "unknown"
        return Counter(roles).most_common(1)[0][0]

    def _module_id(self, path: str, role: SourceRole) -> str:
        parts = [part for part in path.strip("/").split("/") if part]
        if role in {"controller", "route"}:
            return "module:api"
        if role == "service":
            return "module:services"
        if role == "repository":
            return "module:repositories"
        if role in {"model", "dto", "interface", "enum"}:
            return "module:domain"
        if role == "configuration":
            return "module:configuration"
        if role == "test":
            return "module:tests"
        if role == "documentation":
            return "module:documentation"
        if parts and parts[0] in {"app", "src", "backend", "frontend"} and len(parts) > 1:
            return f"module:{parts[1].lower()}"
        return f"module:{parts[0].lower() if parts else 'repository'}"

    def _layer(self, role: SourceRole) -> str:
        if role in {"entrypoint", "controller", "route"}:
            return "presentation"
        if role == "service":
            return "business-logic"
        if role in {"model", "dto", "interface", "enum"}:
            return "domain"
        if role in {"repository", "configuration", "test"}:
            return "infrastructure"
        return "shared"

    def _path_prefix(self, files: list[SourceFileIntelligence]) -> str:
        if not files:
            return "/"
        parts = [file.path.strip("/").split("/") for file in files]
        prefix: list[str] = []
        for columns in zip(*parts):
            if len(set(columns)) == 1:
                prefix.append(columns[0])
            else:
                break
        return "/" + "/".join(prefix) if prefix else "/"

    def _knowledge_graph(
        self,
        repository_id: str,
        repository_name: str,
        modules: list[RepositoryModule],
        files: list[SourceFileIntelligence],
        symbols: list[SourceSymbol],
        dependencies: list[RepositoryDependency],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> KnowledgeGraph:
        nodes: list[KnowledgeGraphNode] = [KnowledgeGraphNode(id=f"repository:{repository_id}", type="repository", name=repository_name)]
        relationships: list[KnowledgeGraphRelationship] = []
        module_by_id = {module.id: module for module in modules}

        for module in modules:
            self._check_cancelled(check_cancelled)
            nodes.append(KnowledgeGraphNode(id=module.id, type="module", name=module.name, path=module.path_prefix, metadata={"role": module.role, "layer": module.layer}))
            relationships.append(self._relationship(f"repository:{repository_id}", module.id, "contains", [module.path_prefix]))

        for file in files:
            self._check_cancelled(check_cancelled)
            file_id = self._file_id(file.path)
            nodes.append(KnowledgeGraphNode(id=file_id, type="file", name=file.name, path=file.path, metadata={"role": file.role, "language": file.language or "Unknown"}))
            if file.module_id in module_by_id:
                relationships.append(self._relationship(file.module_id, file_id, "contains", [file.path]))
            for import_name in file.imports:
                self._check_cancelled(check_cancelled)
                dependency = self._dependency_for_import(import_name, dependencies)
                target = dependency.id if dependency else f"external:{import_name}"
                if dependency is None:
                    nodes.append(KnowledgeGraphNode(id=target, type="dependency", name=import_name, metadata={"external": True}))
                relationships.append(self._relationship(file_id, target, "imports", [file.path]))

        seen_nodes = {node.id for node in nodes}
        for symbol in symbols:
            self._check_cancelled(check_cancelled)
            nodes.append(KnowledgeGraphNode(id=symbol.id, type="symbol", name=symbol.name, path=symbol.file_path, metadata={"kind": symbol.kind, "exported": symbol.exported}))
            relationships.append(self._relationship(self._file_id(symbol.file_path), symbol.id, "contains", [symbol.file_path]))
            if symbol.exported:
                relationships.append(self._relationship(self._file_id(symbol.file_path), symbol.id, "exports", [symbol.file_path]))
            seen_nodes.add(symbol.id)

        for dependency in dependencies:
            self._check_cancelled(check_cancelled)
            if dependency.id not in seen_nodes:
                nodes.append(
                    KnowledgeGraphNode(
                        id=dependency.id,
                        type="dependency",
                        name=dependency.name,
                        path=dependency.source_file,
                        metadata={
                            "version": dependency.version,
                            "ecosystem": dependency.ecosystem,
                            "type": dependency.type,
                            "declarations": [
                                declaration.model_dump(mode="json", by_alias=True)
                                for declaration in dependency.declarations
                            ],
                        },
                    )
                )
                seen_nodes.add(dependency.id)
            relationships.append(
                self._relationship(
                    f"repository:{repository_id}",
                    dependency.id,
                    "depends_on",
                    [declaration.manifest_path for declaration in dependency.declarations],
                )
            )

        deduped_nodes = list({node.id: node for node in nodes}.values())
        deduped_relationships = list({relationship.id: relationship for relationship in relationships}.values())
        return KnowledgeGraph(nodes=deduped_nodes, relationships=deduped_relationships)

    def _dependency_for_import(self, import_name: str, dependencies: list[RepositoryDependency]) -> RepositoryDependency | None:
        normalized = import_name.split("/")[0] if not import_name.startswith("@") else "/".join(import_name.split("/")[:2])
        for dependency in dependencies:
            if dependency.name == normalized or dependency.name == import_name:
                return dependency
        return None

    def _relationship(self, source: str, target: str, rel_type: str, evidence: list[str]) -> KnowledgeGraphRelationship:
        return KnowledgeGraphRelationship(
            id=f"{rel_type}:{source}->{target}",
            source=source,
            target=target,
            type=rel_type,  # type: ignore[arg-type]
            evidence=evidence,
        )

    def _file_id(self, path: str) -> str:
        return f"file:{path}"

    def _symbol_id(self, path: str, name: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9_.@/-]", "-", name)
        return f"symbol:{path}:{safe_name}"
