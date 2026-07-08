from dataclasses import dataclass


@dataclass(frozen=True)
class SyntaxParseResult:
    language: str | None
    symbols: list[str]


class TreeSitterParser:
    """Thin integration point for future language-specific tree-sitter grammars."""

    def parse_symbols(self, content: bytes, extension: str | None) -> SyntaxParseResult:
        if not extension or not content:
            return SyntaxParseResult(language=None, symbols=[])
        return SyntaxParseResult(language=self._language_from_extension(extension), symbols=[])

    def _language_from_extension(self, extension: str) -> str | None:
        return {
            "py": "Python",
            "ts": "TypeScript",
            "tsx": "TypeScript",
            "js": "JavaScript",
            "jsx": "JavaScript",
            "go": "Go",
            "rs": "Rust",
            "java": "Java",
        }.get(extension)
