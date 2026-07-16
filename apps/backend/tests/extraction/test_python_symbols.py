from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _keys(source: str):
    result = EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))
    return {n.stable_key for n in result.nodes if n.node_kind == "symbol"}, result


def test_class_method_and_nested_function_qualified_names():
    keys, _ = _keys(
        "class AuthController:\n"
        "    def login(self):\n"
        "        pass\n"
        "def outer():\n"
        "    def _inner():\n"
        "        pass\n"
    )
    assert "app/api/auth.py::AuthController" in keys
    assert "app/api/auth.py::AuthController.login" in keys
    assert "app/api/auth.py::outer" in keys
    assert "app/api/auth.py::outer._inner" in keys


def test_duplicate_defs_get_discriminator_and_diagnostic():
    keys, result = _keys("def handler():\n    pass\ndef handler():\n    pass\n")
    assert "app/api/auth.py::handler" in keys
    assert "app/api/auth.py::handler#2" in keys
    assert any(d.code == "RI-KEY-DUP-SYMBOL" for d in result.diagnostics)


def test_each_symbol_has_a_definition_observation():
    _, result = _keys("def get_current_user():\n    pass\n")
    defs = [o for o in result.observations if o.observed_kind == "definition"]
    assert any(o.subject_key == "app/api/auth.py::get_current_user" for o in defs)
