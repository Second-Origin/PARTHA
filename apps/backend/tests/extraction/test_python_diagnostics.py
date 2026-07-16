from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _codes(source: str):
    result = EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))
    return [d.code for d in result.diagnostics], result


def test_star_import_is_flagged_unsupported():
    codes, result = _codes("from os import *\n")
    assert "RI-EXT-UNSUPPORTED" in codes
    # star import must not appear as a normal import observation
    assert all(o.referent_text != "*" for o in result.observations)


def test_dynamic_import_is_flagged():
    codes, _ = _codes("import importlib\nm = importlib.import_module('os')\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_bare_imported_import_module_is_flagged():
    # `from importlib import import_module` then a bare call is the same blind
    # spot as the attribute form; the matrix promises a diagnostic for both.
    codes, _ = _codes("from importlib import import_module\nm = import_module('os')\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_bare_dunder_import_is_flagged():
    codes, _ = _codes("m = __import__('os')\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_reflection_is_flagged():
    codes, _ = _codes("x = getattr(object(), 'name', None)\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_syntax_error_is_malformed_and_yields_no_symbols():
    result = EXTRACTOR.extract("bad.py", b"def broken(:\n")
    assert [d.code for d in result.diagnostics] == ["RI-SRC-MALFORMED"]
    assert result.nodes == () and result.observations == ()
