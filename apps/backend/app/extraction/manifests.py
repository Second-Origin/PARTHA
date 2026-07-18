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


class _ManifestStructureError(Exception):
    """A manifest decoded cleanly but is not a supported dependency structure.

    Raised by the section readers when a top-level root, a dependency section,
    or an individual entry has an unexpected type, or when an exact declaration
    line cannot be located.  It is caught alongside the decoder errors so every
    such case fails closed as ``RI-SRC-MALFORMED`` rather than escaping as an
    ``AttributeError``/``TypeError`` or degrading to a silent empty result.
    """


class _JsonNode:
    """A parsed JSON value carrying the source line of each object key.

    ``value`` is a ``dict`` of ``{key: _JsonNode}`` for objects, a ``list`` of
    ``_JsonNode`` for arrays, or the decoded scalar otherwise. ``key_lines`` maps
    an object's own keys to their 1-based declaration line.
    """

    __slots__ = ("value", "key_lines", "line")

    def __init__(self, value: object, key_lines: dict[str, int], line: int | None = None) -> None:
        self.value = value
        self.key_lines = key_lines
        self.line = line


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
        if not isinstance(parsed, dict):
            raise _ManifestStructureError("package.json root is not an object")
        member_lines = DependencyManifestExtractor._json_object_member_lines(text)
        declarations: list[tuple[str, str, int]] = []
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
                declarations.append(("npm", str(name), line))
        return declarations

    @staticmethod
    def _pyproject_declarations(text: str) -> list[tuple[str, str, int]]:
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
        element_lines = DependencyManifestExtractor._toml_project_dependency_element_lines(text)
        # tomllib preserves array order, and the scanner walks the same array in
        # source order, so the i-th string value pairs with the i-th line span.
        if element_lines is None or len(element_lines) != len(values):
            raise _ManifestStructureError("pyproject project.dependencies lines could not be located")
        declarations: list[tuple[str, str, int]] = []
        for value, line in zip(values, element_lines):
            name = DependencyManifestExtractor._python_requirement_name(value)
            if name:
                declarations.append(("pypi", name, line))
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

    # --- Exact declaration spans (RFC §6) ----------------------------------
    #
    # Provenance must point at the real declaration, so line lookup is
    # structure-aware rather than a substring search: JSON keys are located
    # inside their own section object, and TOML dependency strings are read as
    # ordered array elements with brackets inside strings ignored.

    @staticmethod
    def _json_object_member_lines(text: str) -> dict[str, dict[str, int]]:
        """Map ``{section: {member_key: line}}`` for each object-valued member.

        Only the top-level object and its object-valued members are indexed —
        exactly the npm dependency sections. ``text`` has already parsed as JSON
        (``json.loads`` gates malformed input), so the scan is string-aware and
        does not re-validate. Braces and colons inside string literals never
        affect nesting.
        """

        tokens = DependencyManifestExtractor._json_tokens(text)
        root, _ = DependencyManifestExtractor._json_parse(tokens, 0)
        result: dict[str, dict[str, int]] = {}
        if isinstance(root.value, dict):
            for key, child in root.value.items():
                if isinstance(child.value, dict):
                    result[key] = dict(child.key_lines)
        return result

    @staticmethod
    def _json_tokens(text: str) -> list[tuple[str, object, int]]:
        """Tokenize valid JSON into ``(kind, value, line)`` triples.

        ``kind`` is ``"str"`` (decoded string), ``"punct"`` (one of ``{}[]:,``),
        or ``"other"`` (number/true/false/null). Line numbers are 1-based.
        """

        tokens: list[tuple[str, object, int]] = []
        i, n, line = 0, len(text), 1
        while i < n:
            c = text[i]
            if c == "\n":
                line += 1
                i += 1
            elif c in " \t\r":
                i += 1
            elif c == '"':
                start, start_line, j = i, line, i + 1
                while j < n:
                    if text[j] == "\\":
                        j += 2
                        continue
                    if text[j] == '"':
                        j += 1
                        break
                    if text[j] == "\n":
                        line += 1
                    j += 1
                try:
                    value: object = json.loads(text[start:j])
                except json.JSONDecodeError:
                    value = text[start + 1 : max(start + 1, j - 1)]
                tokens.append(("str", value, start_line))
                i = j
            elif c in "{}[]:,":
                tokens.append(("punct", c, line))
                i += 1
            else:
                start = i
                while i < n and text[i] not in " \t\r\n{}[]:,\"":
                    i += 1
                tokens.append(("other", text[start:i], line))
        return tokens

    @staticmethod
    def _json_parse(tokens: list[tuple[str, object, int]], pos: int) -> tuple["_JsonNode", int]:
        kind, value, line = tokens[pos]
        if kind == "punct" and value == "{":
            pos += 1
            members: dict[str, _JsonNode] = {}
            key_lines: dict[str, int] = {}
            while not (tokens[pos][0] == "punct" and tokens[pos][1] == "}"):
                key_value, key_line = tokens[pos][1], tokens[pos][2]
                pos += 2  # consume the key string and its ':'
                child, pos = DependencyManifestExtractor._json_parse(tokens, pos)
                if isinstance(key_value, str):
                    members[key_value] = child
                    key_lines[key_value] = key_line
                if tokens[pos][0] == "punct" and tokens[pos][1] == ",":
                    pos += 1
            return _JsonNode(members, key_lines), pos + 1
        if kind == "punct" and value == "[":
            pos += 1
            items: list[_JsonNode] = []
            while not (tokens[pos][0] == "punct" and tokens[pos][1] == "]"):
                child, pos = DependencyManifestExtractor._json_parse(tokens, pos)
                items.append(child)
                if tokens[pos][0] == "punct" and tokens[pos][1] == ",":
                    pos += 1
            return _JsonNode(items, {}), pos + 1
        return _JsonNode(value, {}, line), pos + 1

    @staticmethod
    def _toml_project_dependency_element_lines(text: str) -> list[int] | None:
        """Return the source line of each ``[project].dependencies`` array element.

        Elements are returned in source order so they pair positionally with the
        values ``tomllib`` parsed. Scanning is string-aware: ``[`` / ``]`` inside
        a dependency string (``"httpx[socks]"``) do not change array nesting, and
        both inline and multi-line arrays are supported. Returns ``None`` when the
        array cannot be located, so the caller fails closed instead of guessing.
        """

        start = DependencyManifestExtractor._toml_dependencies_offset(text)
        if start is None:
            return None
        offset, line = start
        n = len(text)
        depth = 0
        entered = False
        element_lines: list[int] = []
        i = offset
        while i < n:
            c = text[i]
            if c == "\n":
                line += 1
                i += 1
            elif c == "#":
                while i < n and text[i] != "\n":
                    i += 1
            elif c == "[":
                depth += 1
                entered = True
                i += 1
            elif c == "]":
                depth -= 1
                i += 1
                if depth == 0:
                    break
            elif c in "\"'" and depth == 1:
                element_lines.append(line)
                i, line = DependencyManifestExtractor._toml_skip_string(text, i, line)
            elif c in "\"'":
                i, line = DependencyManifestExtractor._toml_skip_string(text, i, line)
            else:
                i += 1
        if not entered:
            return None
        return element_lines

    @staticmethod
    def _toml_dependencies_offset(text: str) -> tuple[int, int] | None:
        """Find the offset/line just past the ``project.dependencies`` ``=``.

        Tracks the active TOML table so only the ``[project]`` table's
        ``dependencies`` key (or a top-level ``project.dependencies`` dotted key)
        is matched, never ``[tool.poetry.dependencies]`` or an unrelated table.
        """

        offset = 0
        current_table = ""
        for raw in text.split("\n"):
            stripped = raw.strip()
            header = re.match(r"\[\[?\s*(.+?)\s*\]\]?\s*(?:#.*)?$", stripped)
            if header and not stripped.startswith("#"):
                current_table = header.group(1).strip().strip("\"'")
            else:
                key = re.match(r"(?:(project)\s*\.\s*)?dependencies\s*=", stripped)
                if key is not None and (key.group(1) == "project" or current_table == "project"):
                    equals = raw.index("=", raw.find("dependencies"))
                    line = text.count("\n", 0, offset) + 1
                    return offset + equals + 1, line
            offset += len(raw) + 1
        return None

    @staticmethod
    def _toml_skip_string(text: str, i: int, line: int) -> tuple[int, int]:
        """Advance past a TOML basic/literal string (single or triple quoted)."""

        quote = text[i]
        triple = text[i : i + 3] in ('"""', "'''")
        if triple:
            delimiter = text[i : i + 3]
            j = i + 3
            while j < len(text) and text[j : j + 3] != delimiter:
                if text[j] == "\n":
                    line += 1
                j += 1
            return j + 3, line
        literal = quote == "'"
        j = i + 1
        while j < len(text):
            if not literal and text[j] == "\\":
                j += 2
                continue
            if text[j] == quote:
                j += 1
                break
            if text[j] == "\n":
                line += 1
            j += 1
        return j, line
