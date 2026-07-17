"""RFC §6.4 ordinal conformance for both extractors.

``ordinal`` is the one-based source order among observations whose *other*
identity fields are identical — it is not a file-wide sequence. These tests pin
that distinction and the resulting observation identities.
"""

from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence import canonical

PY = PythonExtractor()
TS = TypeScriptExtractor()

REVISION_KIND = "upload"
REVISION_VALUE = "sha256:" + "a" * 64


def _imports(result):
    return [o for o in result.observations if o.observed_kind == "import"]


def _observation_id(obs, extractor: str) -> str:
    return canonical.compute_observation_id(
        revision_kind=REVISION_KIND,
        revision_value=REVISION_VALUE,
        observed_kind=obs.observed_kind,
        subject_kind=obs.subject_kind,
        subject_key=obs.subject_key,
        referent_text=obs.referent_text,
        ordinal=obs.ordinal,
        evidence={
            "path": obs.evidence.path,
            "start_line": obs.evidence.start_line,
            "end_line": obs.evidence.end_line,
            "extractor": extractor,
            "extractor_version": "1.0.0",
        },
    )


def test_python_distinct_imports_each_start_at_ordinal_one():
    # Different referent_text and different spans => different identity, so each
    # is the first of its own group. A global 1,2,3 counter would be wrong.
    result = PY.extract("app/api/auth.py", b"import os\nimport sys\nimport json\n")
    assert [o.ordinal for o in _imports(result)] == [1, 1, 1]


def test_python_identical_imports_on_one_line_get_sequential_ordinals():
    # `import os, os` produces two observations with identical identity fields
    # (same referent, same span) — precisely the case ordinal disambiguates.
    result = PY.extract("app/api/auth.py", b"import os, os\n")
    assert [o.ordinal for o in _imports(result)] == [1, 2]


def test_python_definitions_each_start_at_ordinal_one():
    result = PY.extract("app/api/auth.py", b"def a():\n    pass\ndef b():\n    pass\n")
    defs = [o for o in result.observations if o.observed_kind == "definition"]
    assert [o.ordinal for o in defs] == [1, 1]


def test_typescript_distinct_imports_each_start_at_ordinal_one():
    result = TS.extract(
        "src/auth/service.ts",
        b"import { a } from './x';\nimport { b } from './y';\n",
    )
    assert [o.ordinal for o in _imports(result)] == [1, 1]


def test_typescript_identical_imports_on_one_line_get_sequential_ordinals():
    result = TS.extract(
        "src/auth/service.ts",
        b"import { a } from './x'; import { b } from './x';\n",
    )
    assert [o.ordinal for o in _imports(result)] == [1, 2]


def test_identical_identity_fields_yield_distinct_observation_ids():
    # Ordinal is the only thing separating these two; identity must still differ.
    result = PY.extract("app/api/auth.py", b"import os, os\n")
    first, second = _imports(result)
    assert _observation_id(first, "python-ast") != _observation_id(second, "python-ast")


def test_python_import_observation_id_vector():
    """Pin the identity of a known observation against silent drift.

    The hash is generated from this implementation, not derived independently, so
    it proves stability rather than correctness: any change to the identity
    document, the ordinal rule, or the module key changes it and must be a
    deliberate `ri.v1` decision rather than an accident.
    """

    result = PY.extract("app/api/auth.py", b"import os\n")
    obs = _imports(result)[0]
    assert obs.subject_key == "mod:app/api"
    assert obs.ordinal == 1
    assert _observation_id(obs, "python-ast") == (
        "obs:sha256:69232f1caf94a56a33653a1f570dad4b31765ed0a27c2e0d28955756dc2934e3"
    )
