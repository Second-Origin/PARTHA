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


def test_escaping_source_path_yields_diagnostic_not_crash():
    result = EXTRACTOR.extract("../evil.py", b"import os\n")
    assert result.nodes == ()
    assert [d.code for d in result.diagnostics] == ["RI-SEC-PATH-ESCAPE"]


def test_relative_imports_preserve_level_in_referent_text():
    result = _extract("from . import foo\nfrom .config import X\nimport os\n")
    imports = [
        o.referent_text for o in result.observations if o.observed_kind == "import"
    ]
    assert ".foo" in imports
    assert ".config.X" in imports
    assert "os" in imports


def test_from_import_aliases_are_preserved_for_the_resolver():
    result = _extract("from .tokens import issue_token as mint\nmint()\n")
    bindings = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind == "import_binding"
    ]
    assert bindings == [".tokens|issue_token|mint"]


def test_direct_named_calls_become_resolver_observations():
    result = _extract("def caller():\n    return target()\n")
    calls = [
        (observation.subject_key, observation.referent_text)
        for observation in result.observations
        if observation.observed_kind == "call"
    ]
    assert calls == [("mod:app/api", "target")]


def test_parameter_shadowing_is_recorded_at_the_call_site():
    result = _extract(
        "def target():\n    return 1\n"
        "def caller(target):\n    return target()\n"
    )
    shadowed = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind == "call_shadowed"
    ]
    assert shadowed == ["target"]


def test_bare_builtin_calls_produce_no_call_observation():
    """#392: a call to print/len/isinstance/... has no in-repo target and is
    not a relationship worth a resolver diagnostic -- it must not even reach
    the resolver as an observation, unlike a genuine unresolved call."""
    result = _extract(
        "def caller(items):\n"
        "    print(items)\n"
        "    return len(items), isinstance(items, list), sorted(items)\n"
    )
    calls = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind in ("call", "call_shadowed")
    ]
    assert calls == []


def test_genuinely_undefined_call_is_unaffected_by_the_builtin_skip():
    result = _extract("def caller():\n    return someUndefinedThing()\n")
    calls = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind == "call"
    ]
    assert calls == ["someUndefinedThing"]


def test_module_level_shadow_of_a_builtin_still_yields_a_call_observation():
    """A user's own top-level ``def print(...)`` is a real, resolvable symbol
    -- the builtin skip must not treat its name as an untracked builtin just
    because the name also happens to be one."""
    result = _extract("def print(*args):\n    pass\n\n\ndef caller():\n    print('hi')\n")
    calls = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind == "call"
    ]
    assert calls == ["print"]


def test_function_local_import_is_not_exposed_as_a_file_wide_binding():
    result = _extract(
        "def first():\n"
        "    from .tokens import issue_token\n"
        "    return issue_token()\n"
        "def second():\n"
        "    return issue_token()\n"
    )
    assert [
        observation
        for observation in result.observations
        if observation.observed_kind == "import_binding"
    ] == []
    assert [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind == "call_shadowed"
    ] == ["issue_token"]
