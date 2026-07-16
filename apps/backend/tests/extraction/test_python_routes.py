from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _extract(source: str):
    return EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))


def test_decorators_are_recorded_as_a_symbol_property():
    result = _extract(
        "import functools\n"
        "@functools.cache\n"
        "def compute():\n"
        "    pass\n"
    )
    compute = next(
        n for n in result.nodes
        if n.stable_key == "app/api/auth.py::compute"
    )
    assert compute.properties is not None
    assert "functools.cache" in compute.properties["decorators"]


def test_fastapi_route_decorator_yields_literal_path_observation():
    result = _extract(
        "router = APIRouter(prefix='/auth')\n"
        "@router.post('/login')\n"
        "def login():\n"
        "    pass\n"
    )
    routes = [o for o in result.observations if o.observed_kind == "route"]
    assert len(routes) == 1
    # literal decorator string only; no /auth prefix joined (that is #91)
    assert routes[0].referent_text == "/login"
    assert routes[0].subject_key == "app/api/auth.py::login"
