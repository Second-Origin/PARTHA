"""The published support matrix, enforced behaviorally.

Declaring a construct unsupported is a promise that it produces a diagnostic
rather than silence. Every entry in `unsupported` must therefore have a fixture
here that actually drives the extractor and proves the diagnostic fires — a label
with no implementation behind it fails these tests.
"""

import pytest

from app.extraction.base import RI_EXT_UNSUPPORTED
from app.extraction.python import PythonExtractor
from app.extraction.support_matrix import SUPPORT_MATRIX
from app.extraction.typescript import TypeScriptExtractor

# One fixture per declared Python blind spot: construct -> (path, source)
PYTHON_BLIND_SPOTS = {
    "star-import": ("app/a.py", "from os import *\n"),
    "dynamic-import": ("app/a.py", "import importlib\nm = importlib.import_module('os')\n"),
    "reflection": ("app/a.py", "x = getattr(object(), 'name', None)\n"),
    "monkeypatch": ("app/a.py", "import os\nos.sep = '/'\n"),
    "metaclass": ("app/a.py", "class A(metaclass=Meta):\n    pass\n"),
    "http-dynamic-destination": ("app/a.py", "import requests\n\n\ndef f(host):\n    requests.get(host)\n"),
}

# One fixture per declared TypeScript blind spot: construct -> (path, source)
TYPESCRIPT_BLIND_SPOTS = {
    "dynamic-import": ("src/a.ts", "const m = import('./x');\n"),
    "decorator": ("src/a.ts", "class A {\n  @observable x = 1;\n}\n"),
    "namespace": ("src/a.ts", "namespace N { export const a = 1; }\n"),
    "commonjs-require": ("src/a.ts", "const fs = require('fs');\n"),
    "ambient-module": ("src/a.ts", "declare module 'foo' { }\n"),
    "http-dynamic-destination": (
        "src/a.ts",
        "export function f(host: string) {\n  return fetch(`https://${host}/v1`);\n}\n",
    ),
}


def test_python_matrix_lists_supported_and_unsupported():
    python = SUPPORT_MATRIX["python"]
    assert "module" in python.supported
    assert "import" in python.supported
    assert "function" in python.supported
    assert "class" in python.supported
    assert "decorator" in python.supported
    assert "route" in python.supported
    assert "star-import" in python.unsupported
    assert "dynamic-import" in python.unsupported
    assert "reflection" in python.unsupported
    # nothing appears on both sides
    assert set(python.supported).isdisjoint(python.unsupported)


def test_typescript_matrix_lists_supported_and_unsupported():
    ts = SUPPORT_MATRIX["typescript"]
    for entry in ("file", "import", "export", "function", "class", "interface", "type", "enum", "route"):
        assert entry in ts.supported
    for entry in ("dynamic-import", "decorator", "namespace", "commonjs-require"):
        assert entry in ts.unsupported
    assert set(ts.supported).isdisjoint(ts.unsupported)


def test_every_python_blind_spot_has_a_fixture():
    assert set(PYTHON_BLIND_SPOTS) == set(SUPPORT_MATRIX["python"].unsupported)


def test_every_typescript_blind_spot_has_a_fixture():
    assert set(TYPESCRIPT_BLIND_SPOTS) == set(SUPPORT_MATRIX["typescript"].unsupported)


@pytest.mark.parametrize("construct", sorted(PYTHON_BLIND_SPOTS))
def test_python_blind_spot_emits_a_diagnostic(construct):
    path, source = PYTHON_BLIND_SPOTS[construct]
    result = PythonExtractor().extract(path, source.encode("utf-8"))
    assert any(d.code == RI_EXT_UNSUPPORTED for d in result.diagnostics), (
        f"{construct!r} is declared unsupported but emits no diagnostic"
    )


def test_unsupported_reflection_does_not_become_resolver_input():
    result = PythonExtractor().extract("app/a.py", b"x = getattr(object(), 'name', None)\n")

    assert not [
        observation
        for observation in result.observations
        if observation.observed_kind == "call" and observation.referent_text == "getattr"
    ]


def test_unsupported_commonjs_require_does_not_become_resolver_input():
    result = TypeScriptExtractor().extract("src/a.ts", b"const fs = require('fs');\n")

    assert not [observation for observation in result.observations if observation.observed_kind == "call"]


@pytest.mark.parametrize("construct", sorted(TYPESCRIPT_BLIND_SPOTS))
def test_typescript_blind_spot_emits_a_diagnostic(construct):
    path, source = TYPESCRIPT_BLIND_SPOTS[construct]
    result = TypeScriptExtractor().extract(path, source.encode("utf-8"))
    assert any(d.code == RI_EXT_UNSUPPORTED for d in result.diagnostics), (
        f"{construct!r} is declared unsupported but emits no diagnostic"
    )


@pytest.mark.parametrize("construct", sorted(PYTHON_BLIND_SPOTS))
def test_python_blind_spot_diagnostics_are_non_fatal_and_named(construct):
    path, source = PYTHON_BLIND_SPOTS[construct]
    result = PythonExtractor().extract(path, source.encode("utf-8"))
    for diagnostic in result.diagnostics:
        assert diagnostic.severity in ("info", "warning", "error")
        assert diagnostic.message
