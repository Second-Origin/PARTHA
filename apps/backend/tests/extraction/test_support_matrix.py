from app.extraction.support_matrix import SUPPORT_MATRIX


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
