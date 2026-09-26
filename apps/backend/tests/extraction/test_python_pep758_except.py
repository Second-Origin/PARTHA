"""Python 3.14 (PEP 758) ``except A, B:`` must not make a file "malformed" (#471)."""

from __future__ import annotations

from app.extraction.python import PythonExtractor

_PEP_758 = (
    b"def get_current_user(token):\n"
    b"    try:\n"
    b"        return decode(token)\n"
    b"    except InvalidTokenError, ValidationError:\n"
    b"        return None\n"
)


def _extract(source: bytes, path: str = "app/deps.py"):
    return PythonExtractor().extract(path, source)


def test_unparenthesized_multi_exception_clause_is_parsed():
    result = _extract(_PEP_758)

    assert [node.name for node in result.nodes if node.node_kind == "symbol"] == ["get_current_user"]
    assert not [d for d in result.diagnostics if d.code == "RI-SRC-MALFORMED"]


def test_evidence_lines_are_unchanged_by_the_rewrite():
    result = _extract(b"# header\n\n" + _PEP_758)

    symbol = next(node for node in result.nodes if node.node_kind == "symbol")
    assert symbol.evidence[0].start_line == 3


def test_a_clause_that_is_still_invalid_stays_malformed():
    # ``as`` with several types is invalid even on 3.14, and other syntax
    # errors are unrelated to the rewrite.
    for source in (
        b"try:\n    pass\nexcept A, B as error:\n    pass\n",
        b"def broken(:\n    pass\n",
    ):
        result = _extract(source)

        assert [d.code for d in result.diagnostics] == ["RI-SRC-MALFORMED"]


def test_valid_source_is_untouched():
    result = _extract(b"try:\n    pass\nexcept (A, B):\n    pass\n\n\ndef ok():\n    return 1\n")

    assert [node.name for node in result.nodes if node.node_kind == "symbol"] == ["ok"]
