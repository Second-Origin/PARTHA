from pathlib import Path

import pytest

from app.parsers.repository_parser import RepositoryFileLimitExceeded, RepositoryParser


def test_repository_parser_detects_basic_typescript_project(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.tsx").write_text("import React from 'react';", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Example", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}', encoding="utf-8")

    tree, meta, total_size = RepositoryParser().parse(tmp_path)

    assert tree
    assert meta.language == "TypeScript"
    assert meta.framework == "React"
    assert meta.has_readme is True
    assert meta.entry_point == "/src/main.tsx"
    assert total_size > 0


def test_repository_parser_stops_traversal_as_soon_as_file_limit_is_exceeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    first = tmp_path / "a-first"
    first.mkdir()
    (first / "one.py").write_text("one", encoding="utf-8")
    (first / "two.py").write_text("two", encoding="utf-8")
    untouched = tmp_path / "z-untouched"
    untouched.mkdir()
    (untouched / "three.py").write_text("three", encoding="utf-8")

    original_iterdir = Path.iterdir

    def tracked_iterdir(path: Path):
        if path == untouched:
            raise AssertionError("parser traversed beyond the exceeded budget")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", tracked_iterdir)

    with pytest.raises(RepositoryFileLimitExceeded) as caught:
        RepositoryParser().parse(tmp_path, max_file_count=1)

    assert caught.value.file_count == 2
    assert caught.value.max_file_count == 1


def test_repository_parser_does_not_count_ignored_directories(tmp_path: Path):
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    for index in range(5):
        (ignored / f"dependency-{index}.js").write_text("ignored", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")

    tree, meta, _ = RepositoryParser().parse(tmp_path, max_file_count=1)

    assert meta.total_files == 1
    assert [node.name for node in tree] == ["main.py"]
