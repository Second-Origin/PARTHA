"""Observed direct-dependency extraction for the #91 resolver.

The legacy intelligence engine reads manifests from a working directory.  This
extractor instead receives the immutable source bytes selected for a snapshot,
so its dependency observations are safe inputs to ``RelationshipResolver``.
"""

from __future__ import annotations

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
from app.intelligence import canonical


_NPM_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


class DependencyManifestExtractor:
    """Extract direct npm/PyPI declarations as observed dependency facts."""

    name = "dependency-manifest"
    version = "1.0.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return posixpath.basename(path) in {"package.json", "pyproject.toml", "requirements.txt"}

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
        except (json.JSONDecodeError, tomllib.TOMLDecodeError):
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SRC_MALFORMED,
                        category="malformed source",
                        severity="error",
                        message="dependency manifest could not be parsed",
                        path=normalized_path,
                    ),
                )
            )

        nodes: list[ExtractedNode] = []
        observations: list[ExtractedObservation] = []
        diagnostics: list[ExtractedDiagnostic] = []
        for ecosystem, name, line in declarations:
            stable_key = self._dependency_key(ecosystem, name)
            evidence, diagnostic = build_evidence(
                normalized_path, line, line, line_count, producer=self.producer
            )
            if evidence is None:
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
                continue
            nodes.append(
                ExtractedNode(
                    node_kind="dependency",
                    stable_key=stable_key,
                    name=name,
                    language=None,
                    evidence=(evidence,),
                )
            )
            observations.append(
                ExtractedObservation(
                    observed_kind="dependency",
                    subject_kind="dependency",
                    subject_key=stable_key,
                    referent_text=name,
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
        if ecosystem == "pypi":
            name = re.sub(r"[-_.]+", "-", name).lower()
        return canonical.normalize_stable_key("dependency", f"dep:{ecosystem}:{name}")

    @staticmethod
    def _npm_declarations(text: str) -> list[tuple[str, str, int]]:
        parsed = json.loads(text)
        declarations: list[tuple[str, str, int]] = []
        for section in _NPM_SECTIONS:
            dependencies = parsed.get(section, {})
            if not isinstance(dependencies, dict):
                continue
            for name in sorted(dependencies):
                declarations.append(("npm", str(name), DependencyManifestExtractor._find_line(text, str(name))))
        return declarations

    @staticmethod
    def _pyproject_declarations(text: str) -> list[tuple[str, str, int]]:
        parsed = tomllib.loads(text)
        values = parsed.get("project", {}).get("dependencies", [])
        if not isinstance(values, list):
            return []
        declarations: list[tuple[str, str, int]] = []
        for value in values:
            name = DependencyManifestExtractor._python_requirement_name(str(value))
            if name:
                declarations.append(("pypi", name, DependencyManifestExtractor._find_line(text, str(value))))
        return declarations

    @staticmethod
    def _requirements_declarations(text: str) -> list[tuple[str, str, int]]:
        declarations: list[tuple[str, str, int]] = []
        for line_number, raw in enumerate(text.splitlines(), start=1):
            value = raw.split("#", 1)[0].strip()
            if not value or value.startswith(("-", ".")):
                continue
            name = DependencyManifestExtractor._python_requirement_name(value)
            if name:
                declarations.append(("pypi", name, line_number))
        return declarations

    @staticmethod
    def _python_requirement_name(value: str) -> str | None:
        name = re.split(r"[\[<>=!~@\s]", value, maxsplit=1)[0].strip()
        return name or None

    @staticmethod
    def _find_line(text: str, needle: str) -> int:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                return line_number
        return 1
