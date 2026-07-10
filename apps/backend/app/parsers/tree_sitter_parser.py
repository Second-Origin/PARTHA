from dataclasses import dataclass


@dataclass(frozen=True)
class SyntaxParseResult:
    language: str | None
    symbols: list[str]


class TreeSitterParser:
    """PLACEHOLDER — tree-sitter extraction is NOT implemented yet.

    This class only maps a file extension to a language name. It never parses
    source or produces symbols: ``parse_symbols`` always returns an empty
    ``symbols`` list. Real tree-sitter TS/Python extraction (with line spans) is
    planned for the graph work (M2). Symbol extraction today is regex-based in
    ``app.intelligence.engine``. Do not treat this as functional syntax parsing.
    """

    def parse_symbols(self, content: bytes, extension: str | None) -> SyntaxParseResult:
        # Always returns symbols=[]: this is a not-yet-implemented placeholder.
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
