"""Observed direct-dependency extraction for the #91 resolver.

The legacy intelligence engine reads manifests from a working directory.  This
extractor instead receives the immutable source bytes selected for a snapshot,
so its dependency observations are safe inputs to ``RelationshipResolver``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import posixpath
import re
import tomllib

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_SRC_MALFORMED,
    RI_SEC_PATH_ESCAPE,
    assign_ordinals,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.extraction.naming import dependency_stable_key
from app.extraction.structured import (
    StructureError as _ManifestStructureError,
    json_object_member_lines,
    toml_project_dependency_element_lines,
)
from app.intelligence import canonical
from app.extraction.support_matrix import supported_manifest_filenames


SUPPORTED_MANIFEST_FILENAMES = supported_manifest_filenames()
_NPM_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
_NPM_DEPENDENCY_TYPES = {
    "dependencies": "production",
    "devDependencies": "development",
    "peerDependencies": "peer",
    "optionalDependencies": "optional",
}


@dataclass(frozen=True)
class _ManifestDeclaration:
    ecosystem: str
    name: str
    version: str | None
    dependency_type: str
    line: int


class DependencyManifestExtractor:
    """Extract direct npm/PyPI declarations as observed dependency facts."""

    name = "dependency-manifest"
    version = "1.2.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return posixpath.basename(path) in SUPPORTED_MANIFEST_FILENAMES

    def extract(self, path: str, source: bytes) -> ExtractionResult:
        text, source_diagnostic = decode_source(path, source, producer=self.producer)
        if text is None:
            return ExtractionResult(diagnostics=(source_diagnostic,))
        try:
            normalized_path = canonical.normalize_repo_path(path)
        except canonical.PathEscapeError:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SEC_PATH_ESCAPE,
                        category="path escape",
                        severity="error",
                        message="source path is absolute or escapes the repository root",
                    ),
                )
            )

        line_count = logical_line_count(text)
        basename = posixpath.basename(normalized_path)
        try:
            if basename == "package.json":
                declarations = self._npm_declarations(text)
            elif basename == "pyproject.toml":
                declarations = self._pyproject_declarations(text)
            else:
                declarations = self._requirements_declarations(text)
        except (json.JSONDecodeError, tomllib.TOMLDecodeError, _ManifestStructureError):
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SRC_MALFORMED,
                        category="malformed source",
                        severity="error",
                        message="dependency manifest could not be parsed or has an unsupported structure",
                        path=normalized_path,
                    ),
                )
            )

        nodes: list[ExtractedNode] = []
        observations: list[ExtractedObservation] = []
        diagnostics: list[ExtractedDiagnostic] = []
        for declaration in declarations:
            stable_key = self._dependency_key(declaration.ecosystem, declaration.name)
            evidence, diagnostic = build_evidence(
                normalized_path, declaration.line, declaration.line, line_count, producer=self.producer
            )
            if evidence is None:
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
                continue
            nodes.append(
                ExtractedNode(
                    node_kind="dependency",
                    stable_key=stable_key,
                    name=declaration.name,
                    language=None,
                    evidence=(evidence,),
                    properties={
                        "ecosystem": declaration.ecosystem,
                        "version": declaration.version,
                        "dependency_type": declaration.dependency_type,
                        "manifest_path": normalized_path,
                        "workspace_path": posixpath.dirname(normalized_path) or ".",
                    },
                )
            )
            observations.append(
                ExtractedObservation(
                    observed_kind="dependency",
                    subject_kind="dependency",
                    subject_key=stable_key,
                    referent_text=declaration.name,
                    ordinal=0,
                    evidence=evidence,
                )
            )
        return ExtractionResult(
            nodes=tuple(nodes),
            observations=assign_ordinals(observations),
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _dependency_key(ecosystem: str, name: str) -> str:
        return dependency_stable_key(ecosystem, name)

    @staticmethod
    def _npm_declarations(text: str) -> list[_ManifestDeclaration]:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise _ManifestStructureError("package.json root is not an object")
        member_lines = json_object_member_lines(text)
        declarations: list[_ManifestDeclaration] = []
        for section in _NPM_SECTIONS:
            if section not in parsed:
                continue
            dependencies = parsed[section]
            if not isinstance(dependencies, dict):
                raise _ManifestStructureError(f"npm {section} is not an object")
            section_lines = member_lines.get(section, {})
            for name in sorted(dependencies):
                if not isinstance(dependencies[name], str):
                    raise _ManifestStructureError(f"npm {section} entry is not a version string")
                # The line must come from this section's own key token, never a
                # first substring hit that a description, script, or the package
                # name could have produced elsewhere in the manifest.
                line = section_lines.get(name)
                if line is None:
                    raise _ManifestStructureError(f"npm {section} declaration line could not be located")
                declarations.append(
                    _ManifestDeclaration(
                        ecosystem="npm",
                        name=str(name),
                        version=dependencies[name],
                        dependency_type=_NPM_DEPENDENCY_TYPES[section],
                        line=line,
                    )
                )
        return declarations

    @staticmethod
    def _pyproject_declarations(text: str) -> list[_ManifestDeclaration]:
        parsed = tomllib.loads(text)
        project = parsed.get("project", {})
        if not isinstance(project, dict):
            raise _ManifestStructureError("pyproject [project] is not a table")
        values = project.get("dependencies", [])
        if not isinstance(values, list):
            raise _ManifestStructureError("pyproject project.dependencies is not an array")
        if not values:
            return []
        for value in values:
            if not isinstance(value, str):
                raise _ManifestStructureError("pyproject dependency entry is not a string")
        element_lines = toml_project_dependency_element_lines(text)
        # tomllib preserves array order, and the scanner walks the same array in
        # source order, so the i-th string value pairs with the i-th line span.
        if element_lines is None or len(element_lines) != len(values):
            raise _ManifestStructureError("pyproject project.dependencies lines could not be located")
        declarations: list[_ManifestDeclaration] = []
        for value, line in zip(values, element_lines):
            name = DependencyManifestExtractor._python_requirement_name(value)
            if name:
                declarations.append(
                    _ManifestDeclaration(
                        ecosystem="pypi",
                        name=name,
                        version=value[len(name) :].strip() or None,
                        dependency_type="production",
                        line=line,
                    )
                )
        return declarations

    @staticmethod
    def _requirements_declarations(text: str) -> list[_ManifestDeclaration]:
        declarations: list[_ManifestDeclaration] = []
        for line_number, raw in enumerate(text.splitlines(), start=1):
            # A fragment is part of a direct-reference specifier (for example
            # ``package @ https://host/archive.whl#sha256=...``).  Only a hash
            # preceded by whitespace starts a requirements-file comment.
            value = raw.strip()
            if not value or value.startswith(("#", "-", ".")):
                continue
            value = re.sub(r"\s+#.*$", "", value).strip()
            name = DependencyManifestExtractor._python_requirement_name(value)
            if name:
                declarations.append(
                    _ManifestDeclaration(
                        ecosystem="pypi",
                        name=name,
                        version=value[len(name) :].strip() or None,
                        dependency_type="production",
                        line=line_number,
                    )
                )
        return declarations

    @staticmethod
    def _python_requirement_name(value: str) -> str | None:
        name = re.split(r"[\[<>=!~@\s]", value, maxsplit=1)[0].strip()
        return name or None

    # --- Exact declaration spans (RFC §6) ----------------------------------
    #
    # Provenance must point at the real declaration, so line lookup is
    # structure-aware rather than a substring search: JSON keys are located
    # inside their own section object, and TOML dependency strings are read as
    # ordered array elements with brackets inside strings ignored. Both scanners
    # live in ``app.extraction.structured`` so the lockfile extractor reads the
    # same structure the same way.
