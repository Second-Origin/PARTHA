from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _extract(path: str, source: str):
    return EXTRACTOR.extract(path, source.encode("utf-8"))


def test_supports_ts_and_tsx_only():
    assert EXTRACTOR.supports("a.ts") is True
    assert EXTRACTOR.supports("a.tsx") is True
    assert EXTRACTOR.supports("a.js") is False
    assert EXTRACTOR.supports("a.py") is False


def test_file_node_has_whole_file_evidence():
    result = _extract("src/main.ts", "const x = 1;\n")
    files = [n for n in result.nodes if n.node_kind == "file"]
    assert len(files) == 1
    assert files[0].stable_key == "file:src/main.ts"
    ev = files[0].evidence[0]
    assert ev.granularity == "file"
    assert (ev.start_line, ev.end_line) == (1, ev.logical_line_count)


def test_binary_file_is_flagged_not_parsed():
    result = _extract("src/blob.ts", "\x00\x00")
    assert [d.code for d in result.diagnostics] == ["RI-SRC-BINARY"]
    assert result.nodes == ()


def test_escaping_path_is_flagged_not_raised():
    result = _extract("../../etc/passwd.ts", "const x = 1;\n")
    assert [d.code for d in result.diagnostics] == ["RI-SEC-PATH-ESCAPE"]
    assert result.nodes == ()


def test_module_node_is_emitted_with_directory_scoped_key():
    # #89 requires module nodes alongside file nodes.
    result = _extract("src/auth/service.ts", "const x = 1;\n")
    modules = [n for n in result.nodes if n.node_kind == "module"]
    assert len(modules) == 1
    assert modules[0].stable_key == "mod:src/auth"
    assert modules[0].name == "auth"
    ev = modules[0].evidence[0]
    assert ev.granularity == "file"
    assert (ev.start_line, ev.end_line) == (1, ev.logical_line_count)


def test_sibling_typescript_files_share_one_module_record():
    # Same directory => byte-identical module record, or the snapshot cannot seal.
    a = _extract("src/auth/service.ts", "const a = 1;\n")
    b = _extract("src/auth/tokens.ts", "const b = 1;\n")
    mod_a = next(n for n in a.nodes if n.node_kind == "module")
    mod_b = next(n for n in b.nodes if n.node_kind == "module")
    assert (mod_a.stable_key, mod_a.name) == (mod_b.stable_key, mod_b.name)


def test_root_level_file_module_has_no_short_name():
    result = _extract("main.ts", "const x = 1;\n")
    module = next(n for n in result.nodes if n.node_kind == "module")
    assert module.stable_key == "mod:"
    assert module.name is None


def test_bare_global_calls_produce_no_call_observation():
    """#392: a call to an ECMAScript/host global has no in-repo target and is
    not a relationship worth a resolver diagnostic -- it must not even reach
    the resolver as an observation, unlike a genuine unresolved call."""
    result = _extract(
        "src/util.ts",
        "function caller(value: string) {\n"
        "  parseInt(value);\n"
        "  structuredClone(value);\n"
        "  setTimeout(() => {}, 0);\n"
        "  return String(value);\n"
        "}\n",
    )
    calls = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind in ("call", "call_shadowed")
    ]
    assert calls == []


def test_genuinely_undefined_call_is_unaffected_by_the_global_skip():
    result = _extract("src/util.ts", "function caller() {\n  return someUndefinedThing();\n}\n")
    calls = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind == "call"
    ]
    assert calls == ["someUndefinedThing"]


def test_function_scoped_shadow_of_a_global_still_yields_a_call_observation():
    """A local function that shadows a global name (e.g. a parameter or inner
    declaration named ``String``) is a real, resolvable local call -- the
    global skip must not swallow it just because the name is also a global."""
    result = _extract(
        "src/util.ts",
        "function caller() {\n"
        "  function String(value: unknown) { return value; }\n"
        "  return String('hi');\n"
        "}\n",
    )
    calls = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind in ("call", "call_shadowed")
    ]
    assert "String" in calls
