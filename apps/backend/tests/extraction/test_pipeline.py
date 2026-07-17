from app.extraction.pipeline import ExtractionPipeline
from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor


def _pipeline(*, max_source_bytes: int = 512 * 1024) -> ExtractionPipeline:
    return ExtractionPipeline(
        (PythonExtractor(), TypeScriptExtractor()),
        max_source_bytes=max_source_bytes,
    )


def test_pipeline_rejects_escaping_paths_before_dispatch():
    runs = _pipeline().run({"..\\escape.py": b"def leaked():\n    pass\n"})
    diagnostics = [diagnostic for run in runs for diagnostic in run.result.diagnostics]
    assert [diagnostic.code for diagnostic in diagnostics] == ["RI-SEC-PATH-ESCAPE"]
    assert not [node for run in runs for node in run.result.nodes]


def test_pipeline_enforces_real_configured_size_budget():
    runs = _pipeline(max_source_bytes=4).run({"src/a.py": b"x = 1\n"})
    nodes = [node for run in runs for node in run.result.nodes]
    diagnostics = [diagnostic for run in runs for diagnostic in run.result.diagnostics]

    assert [diagnostic.code for diagnostic in diagnostics] == ["RI-LIMIT-SKIP"]
    assert diagnostics[0].details == {"budgetBytes": 4, "reportedBytes": 6}
    assert [node.stable_key for node in nodes] == ["repo:root"]


def test_pipeline_emits_repository_root_for_diagnostics_only_text_source():
    runs = _pipeline().run({"src/broken.py": b"def broken(:\n    return\n"})

    nodes = [node for run in runs for node in run.result.nodes]
    diagnostics = [diagnostic for run in runs for diagnostic in run.result.diagnostics]

    root = next(node for node in nodes if node.stable_key == "repo:root")
    assert root.node_kind == "repository"
    assert root.evidence[0].path == "src/broken.py"
    assert root.evidence[0].start_line == root.evidence[0].end_line == 1
    assert [diagnostic.code for diagnostic in diagnostics] == ["RI-SRC-MALFORMED"]


def test_pipeline_uses_supports_and_inventory_for_unsupported_text():
    runs = _pipeline().run({"README.md": b"# title\n", "src/a.py": b"def f():\n    pass\n"})
    producers = [run.producer for run in runs]
    assert producers == ["repository-inventory@1.0.0", "python-ast@1.0.0"]
    nodes = [node for run in runs for node in run.result.nodes]
    assert any(node.stable_key == "file:README.md" for node in nodes)
    assert any(node.stable_key == "src/a.py::f" for node in nodes)
