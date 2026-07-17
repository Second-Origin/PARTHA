from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSupport:
    supported: tuple[str, ...]
    unsupported: tuple[str, ...]


SUPPORT_MATRIX: dict[str, LanguageSupport] = {
    "python": LanguageSupport(
        supported=("module", "import", "function", "class", "method", "decorator", "route"),
        unsupported=("star-import", "dynamic-import", "reflection", "monkeypatch", "metaclass"),
    ),
    "typescript": LanguageSupport(
        supported=(
            "file", "module", "import", "export", "function", "class", "method",
            "interface", "type", "enum", "const", "route",
        ),
        unsupported=("dynamic-import", "decorator", "namespace", "commonjs-require", "ambient-module"),
    ),
    "source": LanguageSupport(
        supported=("repository", "file", "empty-file", "trailing-newline"),
        unsupported=("binary-file", "malformed-source", "large-file", "path-escape"),
    ),
}
