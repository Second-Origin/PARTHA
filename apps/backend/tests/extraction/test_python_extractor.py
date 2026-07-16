from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _extract(source: str):
    return EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))


def test_supports_only_python():
    assert EXTRACTOR.supports("a.py") is True
    assert EXTRACTOR.supports("a.ts") is False


def test_module_node_has_whole_file_evidence():
    result = _extract("import os\n")
    modules = [n for n in result.nodes if n.node_kind == "module"]
    assert len(modules) == 1
    module = modules[0]
    assert module.stable_key == "mod:app/api"
    ev = module.evidence[0]
    assert ev.granularity == "file"
    assert (ev.start_line, ev.end_line) == (1, ev.logical_line_count)


def test_imports_become_observations_with_referent_text():
    result = _extract("import os\nfrom app.core import config\n")
    imports = sorted(
        (o.referent_text for o in result.observations if o.observed_kind == "import")
    )
    assert imports == ["app.core.config", "os"]
    for obs in result.observations:
        if obs.observed_kind == "import":
            assert obs.subject_key == "mod:app/api"
            assert obs.evidence.start_line >= 1
