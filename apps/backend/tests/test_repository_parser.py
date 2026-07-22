from pathlib import Path

import pytest

import app.parsers.repository_parser as repository_parser_module
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


def test_repository_parser_preflight_stops_before_materializing_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class FileEntry:
        def __init__(self, index: int) -> None:
            self.name = f"file-{index}.py"
            self.path = str(tmp_path / self.name)

        def is_dir(self) -> bool:
            return False

        def is_file(self) -> bool:
            return True

    class BoundedScandir:
        def __init__(self) -> None:
            self.index = 0
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

        def __iter__(self):
            return self

        def __next__(self):
            if self.index == 6:
                raise AssertionError("parser requested an entry after the limit was exceeded")
            entry = FileEntry(self.index)
            self.index += 1
            return entry

    entries = BoundedScandir()

    def scandir(path: Path):
        assert path == tmp_path
        return entries

    def unexpected_iterdir(_path: Path):
        raise AssertionError("preflight used Path.iterdir instead of os.scandir")

    monkeypatch.setattr(repository_parser_module.os, "scandir", scandir)
    monkeypatch.setattr(Path, "iterdir", unexpected_iterdir)

    with pytest.raises(RepositoryFileLimitExceeded) as caught:
        RepositoryParser().parse(tmp_path, max_file_count=5)

    assert caught.value.file_count == 6
    assert caught.value.max_file_count == 5
    assert entries.index == 6
    assert entries.closed is True


def test_repository_parser_does_not_count_ignored_directories(tmp_path: Path):
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    for index in range(5):
        (ignored / f"dependency-{index}.js").write_text("ignored", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")

    tree, meta, _ = RepositoryParser().parse(tmp_path, max_file_count=1)

    assert meta.total_files == 1
    assert [node.name for node in tree] == ["main.py"]
