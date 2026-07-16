from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSupport:
    supported: tuple[str, ...]
    unsupported: tuple[str, ...]


SUPPORT_MATRIX: dict[str, LanguageSupport] = {
    "python": LanguageSupport(
        supported=("module", "import", "function", "class", "method", "decorator", "route"),
        unsupported=("star-import", "dynamic-import", "reflection", "metaclass"),
    ),
}
