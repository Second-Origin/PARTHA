"""Direct real-adapter coverage for Issue #94's extraction boundary."""

from __future__ import annotations

from pathlib import Path

from benchmark.adapter import RealExtractionAdapter
from benchmark.facts import EvidenceSpan, Fact
from benchmark.loader import LoadedFixture


def _fixture(
    directory: Path,
    *,
    language: str = "mixed",
    producers: tuple[str, ...] = (
        "python-ast@1.0.0",
        "repository-inventory@1.0.0",
        "typescript-ast@1.0.0",
    ),
    max_source_bytes: int = 512 * 1024,
) -> LoadedFixture:
    return LoadedFixture(
        fixture_id="adapter",
        fixture_class="minimal",
        language=language,
        title="adapter",
        description="direct adapter test",
        directory=directory,
        source_root=".",
        revision_identity="upload-sha256",
        producer_version_set=producers,
        constructs_covered=(),
        deterministic=False,
        expected=(),
        max_source_bytes=max_source_bytes,
    )


def _write(directory: Path, path: str, data: bytes) -> None:
    target = directory / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def test_real_adapter_dispatches_python_typescript_and_tsx(tmp_path: Path):
    _write(tmp_path, "src/a.py", b"def py_name():\n    pass\n")
    _write(tmp_path, "src/b.ts", b"export function tsName() {}\n")
    _write(tmp_path, "src/c.tsx", b"export const view = <div />;\n")

    facts = RealExtractionAdapter().extract(_fixture(tmp_path))

    subjects = {fact.subject for fact in facts if fact.fact_type == "node"}
    assert "src/a.py::py_name" in subjects
    assert "src/b.ts::tsName" in subjects
    assert "src/c.tsx::view" in subjects


def test_unsupported_text_file_is_inventory_only(tmp_path: Path):
    _write(tmp_path, "notes.txt", b"plain text\n")

    facts = RealExtractionAdapter().extract(_fixture(tmp_path))

    note = next(fact for fact in facts if fact.subject == "file:notes.txt")
    assert note.name == "notes.txt"
    assert note.language == ""
    assert note.evidence[0].extractor == "repository-inventory"
    assert not [fact for fact in facts if fact.fact_type == "observation"]


def test_binary_and_malformed_supported_sources_use_real_extractors(tmp_path: Path):
    _write(tmp_path, "src/binary.py", b"\x00binary")
    _write(tmp_path, "src/bad.ts", b"export const broken = ;\n")

    facts = RealExtractionAdapter().extract(_fixture(tmp_path))

    diagnostics = {(fact.kind, fact.producer) for fact in facts if fact.fact_type == "diagnostic"}
    assert ("RI-SRC-BINARY", "python-ast@1.0.0") in diagnostics
    assert ("RI-SRC-MALFORMED", "typescript-ast@1.0.0") in diagnostics


def test_duplicate_symbols_observations_properties_and_provenance_are_preserved(tmp_path: Path):
    _write(
        tmp_path,
        "src/a.py",
        b"@decorator\ndef repeated():\n    pass\ndef repeated():\n    pass\n",
    )

    facts = RealExtractionAdapter().extract(_fixture(tmp_path, language="python"))

    nodes = [fact for fact in facts if fact.fact_type == "node" and "repeated" in fact.subject]
    assert [fact.subject for fact in nodes] == ["src/a.py::repeated", "src/a.py::repeated#2"]
    assert nodes[0].name == "repeated"
    assert nodes[0].language == "python"
    assert nodes[0].value == '{"decorators":["decorator"]}'
    definitions = [fact for fact in facts if fact.fact_type == "observation" and fact.kind == "definition"]
    assert [fact.ordinal for fact in definitions] == [1, 1]
    assert all(fact.evidence[0].extractor == "python-ast" for fact in definitions)
    duplicate = next(fact for fact in facts if fact.kind == "RI-KEY-DUP-SYMBOL")
    assert duplicate.subject == "src/a.py::repeated#2"
    assert duplicate.producer == "python-ast@1.0.0"


def test_real_source_size_policy_emits_limit_diagnostic(tmp_path: Path):
    _write(tmp_path, "src/large.py", b"x = 1\n" * 5)

    facts = RealExtractionAdapter().extract(
        _fixture(tmp_path, max_source_bytes=8)
    )

    diagnostic = next(fact for fact in facts if fact.kind == "RI-LIMIT-SKIP")
    assert diagnostic.producer == "repository-inventory@1.0.0"
    assert diagnostic.subject == "file:src/large.py"
    assert '"budgetBytes":8' in diagnostic.value
    assert not any(fact.subject == "src/large.py::x" for fact in facts)


def test_exact_duplicate_adapter_output_is_not_hidden():
    fact = Fact(
        fact_type="node",
        kind="symbol",
        subject="src/a.py::f",
        name="f",
        language="python",
        truth_class="observed",
        evidence=(EvidenceSpan("src/a.py", 1, 1, "python-ast", "1.0.0", "span"),),
    )

    merged = RealExtractionAdapter._merge_compatible_nodes([fact, fact])

    assert merged == [fact, fact]
