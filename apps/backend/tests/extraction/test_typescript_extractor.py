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
