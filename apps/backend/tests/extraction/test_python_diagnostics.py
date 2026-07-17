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


def test_bare_aliased_import_module_is_flagged():
    codes, _ = _codes("from importlib import import_module as load_module\nm = load_module('os')\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_importlib_module_alias_is_flagged():
    codes, _ = _codes("import importlib as imports\nm = imports.import_module('os')\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_bare_dunder_import_is_flagged():
    codes, _ = _codes("m = __import__('os')\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_reflection_is_flagged():
    codes, _ = _codes("x = getattr(object(), 'name', None)\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_monkeypatching_an_imported_module_is_flagged():
    codes, _ = _codes("import os\nos.sep = '\\\\'\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_monkeypatching_an_imported_class_is_flagged():
    codes, _ = _codes("from models import Thing\nThing.save = None\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_monkeypatching_an_aliased_import_is_flagged():
    codes, _ = _codes("import numpy as np\nnp.array = None\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_monkeypatching_a_nested_attribute_is_flagged():
    codes, _ = _codes("import os\nos.path.join = None\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_augmented_assignment_to_an_import_is_flagged():
    codes, _ = _codes("import config\nconfig.retries += 1\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_tuple_target_with_imported_attribute_is_flagged():
    codes, _ = _codes("import os\nos.sep, value = '/', 1\n")
    assert "RI-EXT-UNSUPPORTED" in codes


# Negative cases: attribute assignment is routine. Only rebinding an attribute on
# a name this file imported is monkey-patching; flagging the rest would make the
# diagnostic noise and train people to ignore it.
def test_self_attribute_assignment_is_not_monkeypatching():
    codes, _ = _codes("class A:\n    def __init__(self):\n        self.x = 1\n")
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_local_object_attribute_assignment_is_not_monkeypatching():
    codes, _ = _codes("class C:\n    pass\nc = C()\nc.x = 1\n")
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_rebinding_an_imported_name_itself_is_not_monkeypatching():
    # Rebinding the local name does not mutate the imported object.
    codes, _ = _codes("import os\nos = None\n")
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_reading_an_imported_attribute_is_not_monkeypatching():
    codes, _ = _codes("import os\np = os.sep\n")
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_parameter_shadowing_import_is_not_monkeypatching():
    source = "import os\ndef configure(os):\n    os.sep = '/'\n"
    codes, _ = _codes(source)
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_local_rebinding_import_is_not_monkeypatching():
    source = "import os\nos = object()\nos.sep = '/'\n"
    codes, _ = _codes(source)
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_local_import_module_definition_is_not_a_dynamic_import():
    source = "def import_module(name):\n    return name\n\nimport_module('local')\n"
    codes, _ = _codes(source)
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_import_module_parameter_and_rebinding_are_not_dynamic_imports():
    parameter_source = "def load(import_module):\n    return import_module('local')\n"
    rebound_source = "from importlib import import_module\nimport_module = lambda name: name\nimport_module('local')\n"
    parameter_codes, _ = _codes(parameter_source)
    rebound_codes, _ = _codes(rebound_source)
    assert "RI-EXT-UNSUPPORTED" not in parameter_codes
    assert "RI-EXT-UNSUPPORTED" not in rebound_codes


def test_unrelated_import_module_method_is_not_a_dynamic_import():
    codes, _ = _codes("class Loader:\n    def import_module(self, name):\n        return name\n\nLoader().import_module('local')\n")
    assert "RI-EXT-UNSUPPORTED" not in codes


def test_syntax_error_is_malformed_and_yields_no_symbols():
    result = EXTRACTOR.extract("bad.py", b"def broken(:\n")
    assert [d.code for d in result.diagnostics] == ["RI-SRC-MALFORMED"]
    assert result.nodes == () and result.observations == ()
