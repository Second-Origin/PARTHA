from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _extract(source: str):
    return EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))


def test_decorators_are_recorded_as_a_symbol_property():
    result = _extract("import functools\n@functools.cache\ndef compute():\n    pass\n")
    compute = next(n for n in result.nodes if n.stable_key == "app/api/auth.py::compute")
    assert compute.properties is not None
    assert "functools.cache" in compute.properties["decorators"]


def test_decorator_observation_carries_the_decorator_own_span():
    # The symbol's evidence starts at `def`, so a decorator on an earlier line is
    # outside it. Each decorator needs provenance for its own source lines (#90).
    result = _extract("@router.post('/login')\n@requires_auth\ndef login():\n    pass\n")
    decorators = [o for o in result.observations if o.observed_kind == "decorator"]
    assert [(o.referent_text, o.evidence.start_line, o.evidence.end_line) for o in decorators] == [
        ("router.post", 1, 1),
        ("requires_auth", 2, 2),
    ]
    assert all(o.subject_key == "app/api/auth.py::login" for o in decorators)


def test_decorated_symbol_evidence_still_starts_at_def():
    result = _extract("@requires_auth\ndef login():\n    pass\n")
    login = next(n for n in result.nodes if n.stable_key == "app/api/auth.py::login")
    assert (login.evidence[0].start_line, login.evidence[0].end_line) == (2, 3)


def test_class_decorators_are_observed():
    result = _extract("@dataclass\nclass Session:\n    pass\n")
    decorators = [o for o in result.observations if o.observed_kind == "decorator"]
    assert [o.referent_text for o in decorators] == ["dataclass"]
    assert decorators[0].evidence.start_line == 1


def test_fastapi_route_decorator_yields_literal_path_observation():
    result = _extract("router = APIRouter(prefix='/auth')\n@router.post('/login')\ndef login():\n    pass\n")
    routes = [o for o in result.observations if o.observed_kind == "route"]
    assert len(routes) == 1
    # literal decorator string only; no /auth prefix joined (that is #91)
    assert routes[0].referent_text == "/login"
    assert routes[0].subject_key == "app/api/auth.py::(anonymous:route#1)"
    handlers = [o for o in result.observations if o.observed_kind == "route_handler"]
    assert [(o.subject_key, o.referent_text) for o in handlers] == [
        ("app/api/auth.py::(anonymous:route#1)", "app/api/auth.py::login")
    ]
