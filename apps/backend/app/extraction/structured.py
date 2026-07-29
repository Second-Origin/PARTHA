"""Structure-aware source scanners shared by the manifest-family extractors.

Provenance must point at the *real* declaration, so every extractor that reads a
structured configuration file needs the exact source line of a decoded value.
Neither :mod:`json` nor :mod:`tomllib` reports line numbers, and a substring
search would happily match a description, a script, or a package name elsewhere
in the file.

These scanners are therefore the single implementation of "where in the source
did this decoded value come from" for ``package.json``, ``pyproject.toml``,
``requirements.txt``, ``package-lock.json``, and ``poetry.lock``. They run
*after* the real decoder has accepted the text, so they locate structure rather
than re-validate it, and they are string-aware: braces, brackets, and ``#``
inside a string literal never affect nesting.

Adding a second copy of this logic inside another extractor is the change most
likely to make two producers disagree about the same file.
"""

from __future__ import annotations

import json
import re


class StructureError(Exception):
    """A file decoded cleanly but is not a supported structure.

    Raised when a root, a section, or an individual entry has an unexpected
    type, or when an exact declaration line cannot be located. Callers catch it
    alongside the decoder errors so every such case fails closed as
    ``RI-SRC-MALFORMED`` rather than escaping as an ``AttributeError`` or
    degrading to a silent empty result.
    """


class JsonNode:
    """A parsed JSON value carrying the source line of each object key.

    ``value`` is a ``dict`` of ``{key: JsonNode}`` for objects, a ``list`` of
    ``JsonNode`` for arrays, or the decoded scalar otherwise. ``key_lines`` maps
    an object's own keys to their 1-based declaration line.
    """

    __slots__ = ("value", "key_lines", "line")

    def __init__(self, value: object, key_lines: dict[str, int], line: int | None = None) -> None:
        self.value = value
        self.key_lines = key_lines
        self.line = line


# --- JSON -------------------------------------------------------------------


def json_object_member_lines(text: str) -> dict[str, dict[str, int]]:
    """Map ``{section: {member_key: line}}`` for each object-valued member.

    Only the top-level object and its object-valued members are indexed — the
    npm dependency sections and ``package-lock.json``'s ``packages`` table.
    ``text`` has already parsed as JSON (``json.loads`` gates malformed input),
    so the scan is string-aware and does not re-validate.
    """

    tokens = json_tokens(text)
    root, _ = _json_parse(tokens, 0)
    result: dict[str, dict[str, int]] = {}
    if isinstance(root.value, dict):
        for key, child in root.value.items():
            if isinstance(child.value, dict):
                result[key] = dict(child.key_lines)
    return result


def json_tokens(text: str) -> list[tuple[str, object, int]]:
    """Tokenize valid JSON into ``(kind, value, line)`` triples.

    ``kind`` is ``"str"`` (decoded string), ``"punct"`` (one of ``{}[]:,``), or
    ``"other"`` (number/true/false/null). Line numbers are 1-based.
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
            while i < n and text[i] not in ' \t\r\n{}[]:,"':
                i += 1
            tokens.append(("other", text[start:i], line))
    return tokens


def _json_parse(tokens: list[tuple[str, object, int]], pos: int) -> tuple[JsonNode, int]:
    kind, value, line = tokens[pos]
    if kind == "punct" and value == "{":
        pos += 1
        members: dict[str, JsonNode] = {}
        key_lines: dict[str, int] = {}
        while not (tokens[pos][0] == "punct" and tokens[pos][1] == "}"):
            key_value, key_line = tokens[pos][1], tokens[pos][2]
            pos += 2  # consume the key string and its ':'
            child, pos = _json_parse(tokens, pos)
            if isinstance(key_value, str):
                members[key_value] = child
                key_lines[key_value] = key_line
            if tokens[pos][0] == "punct" and tokens[pos][1] == ",":
                pos += 1
        return JsonNode(members, key_lines), pos + 1
    if kind == "punct" and value == "[":
        pos += 1
        items: list[JsonNode] = []
        while not (tokens[pos][0] == "punct" and tokens[pos][1] == "]"):
            child, pos = _json_parse(tokens, pos)
            items.append(child)
            if tokens[pos][0] == "punct" and tokens[pos][1] == ",":
                pos += 1
        return JsonNode(items, {}), pos + 1
    return JsonNode(value, {}, line), pos + 1


# --- TOML -------------------------------------------------------------------


def toml_skip_string(text: str, i: int, line: int) -> tuple[int, int]:
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


def toml_array_of_tables_lines(text: str, name: str) -> list[int]:
    """Return the 1-based line of each ``[[name]]`` array-of-tables header.

    Headers are returned in source order, so they pair positionally with the
    list ``tomllib`` parsed for that key. The scan is string- and comment-aware:
    a ``[[package]]`` sequence inside a triple-quoted description or after a
    ``#`` never counts, and ``[[package.files]]`` is not ``[[package]]``.
    """

    lines: list[int] = []
    i, n, line = 0, len(text), 1
    at_line_start = True
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            at_line_start = True
            continue
        if c in " \t\r":
            i += 1
            continue
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c in "\"'":
            i, line = toml_skip_string(text, i, line)
            at_line_start = False
            continue
        if at_line_start and text.startswith("[[", i):
            end = text.find("]]", i + 2)
            newline = text.find("\n", i)
            if end >= 0 and (newline < 0 or end < newline) and text[i + 2 : end].strip().strip("\"'") == name:
                lines.append(line)
                i = end + 2
                at_line_start = False
                continue
        at_line_start = False
        i += 1
    return lines


def toml_project_dependency_element_lines(text: str) -> list[int] | None:
    """Return the source line of each ``[project].dependencies`` array element.

    Elements are returned in source order so they pair positionally with the
    values ``tomllib`` parsed. Scanning is string-aware: ``[`` / ``]`` inside a
    dependency string (``"httpx[socks]"``) do not change array nesting, and both
    inline and multi-line arrays are supported. Returns ``None`` when the array
    cannot be located, so the caller fails closed instead of guessing.
    """

    start = _toml_dependencies_offset(text)
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
            i, line = toml_skip_string(text, i, line)
        elif c in "\"'":
            i, line = toml_skip_string(text, i, line)
        else:
            i += 1
    if not entered:
        return None
    return element_lines


def _toml_dependencies_offset(text: str) -> tuple[int, int] | None:
    """Find the offset/line just past the ``project.dependencies`` ``=``.

    Tracks the active TOML table so only the ``[project]`` table's
    ``dependencies`` key (or a top-level ``project.dependencies`` dotted key) is
    matched, never ``[tool.poetry.dependencies]`` or an unrelated table.
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
