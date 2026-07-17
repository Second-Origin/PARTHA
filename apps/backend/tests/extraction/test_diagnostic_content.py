"""RFC-0001 §13: diagnostic `message`/`details` must not embed source content.

A diagnostic names *what* was unsupported and cites *where* via path + span. It
must never carry the source text itself, because that text can contain secrets
and diagnostics are stored and surfaced. The span is the pointer; the source
stays in the repository.
"""

import pytest

from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor

SECRET = "s3cr3t-token"

# Sources that put a secret literal directly next to a construct that produces a
# diagnostic, in each place an extractor is tempted to quote the source back.
TYPESCRIPT_LEAK_CASES = [
    ('decorator argument', f'class A {{\n  @sealed("{SECRET}")\n  x = 1;\n}}\n'),
    ('decorator on class', f'@Injectable({{ key: "{SECRET}" }})\nclass B {{}}\n'),
    ('namespace body', f'namespace N {{ const k = "{SECRET}"; }}\n'),
    ('require argument', f'const c = require("{SECRET}");\n'),
    ('dynamic import argument', f'const m = import("./{SECRET}");\n'),
]

PYTHON_LEAK_CASES = [
    ('star import', f'from {SECRET.replace("-", "_")} import *\n'),
    ('metaclass', f'class A(metaclass={SECRET.replace("-", "_")}):\n    pass\n'),
    ('reflection argument', f'x = getattr(o, "{SECRET}", None)\n'),
    ('dynamic import argument', f'import importlib\nm = importlib.import_module("{SECRET}")\n'),
]


@pytest.mark.parametrize("label,source", TYPESCRIPT_LEAK_CASES, ids=[c[0] for c in TYPESCRIPT_LEAK_CASES])
def test_typescript_diagnostics_do_not_embed_source(label, source):
    result = TypeScriptExtractor().extract("src/a.ts", source.encode("utf-8"))
    assert result.diagnostics, f"{label}: expected a diagnostic to exist to make this test meaningful"
    for diagnostic in result.diagnostics:
        assert SECRET not in diagnostic.message, f"{label}: secret leaked into message"
        assert SECRET not in str(diagnostic.details or ""), f"{label}: secret leaked into details"


@pytest.mark.parametrize("label,source", PYTHON_LEAK_CASES, ids=[c[0] for c in PYTHON_LEAK_CASES])
def test_python_diagnostics_do_not_embed_source(label, source):
    marker = SECRET.replace("-", "_")
    result = PythonExtractor().extract("app/a.py", source.encode("utf-8"))
    assert result.diagnostics, f"{label}: expected a diagnostic to exist to make this test meaningful"
    for diagnostic in result.diagnostics:
        assert marker not in diagnostic.message, f"{label}: source identifier leaked into message"
        assert SECRET not in diagnostic.message, f"{label}: secret leaked into message"
        assert SECRET not in str(diagnostic.details or ""), f"{label}: secret leaked into details"


def test_diagnostics_still_cite_a_span_for_context():
    # Dropping source text from the message is only acceptable because the span
    # still says exactly where to look.
    result = TypeScriptExtractor().extract("src/a.ts", b'class A {\n  @sealed("x")\n  y = 1;\n}\n')
    unsupported = [d for d in result.diagnostics if d.code == "RI-EXT-UNSUPPORTED"]
    assert unsupported
    for diagnostic in unsupported:
        assert diagnostic.path == "src/a.ts"
        assert diagnostic.span is not None
