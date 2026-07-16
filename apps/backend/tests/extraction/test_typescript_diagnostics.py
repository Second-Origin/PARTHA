from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _codes(source: str, path: str = "src/x.ts"):
    result = EXTRACTOR.extract(path, source.encode("utf-8"))
    return [d.code for d in result.diagnostics]


def test_dynamic_import_flagged():
    assert "RI-EXT-UNSUPPORTED" in _codes("const m = import('./x');\n")


def test_namespace_flagged():
    assert "RI-EXT-UNSUPPORTED" in _codes("namespace N { export const a = 1; }\n")


def test_commonjs_require_flagged():
    assert "RI-EXT-UNSUPPORTED" in _codes("const fs = require('fs');\n")


def test_parse_error_is_malformed():
    assert "RI-SRC-MALFORMED" in _codes("class {{{ broken\n")
