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

        def is_symlink(self) -> bool:
            return False

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


def test_repository_parser_drops_macos_archive_artifacts(tmp_path: Path):
    """#398: __MACOSX/, ._<name> AppleDouble sidecars, and .DS_Store are
    archiver/Finder bookkeeping, not repository content -- an AppleDouble
    sidecar in particular shares its real counterpart's extension
    (``._app.py`` next to ``app.py``) while being opaque binary, so it must
    never reach a downstream extension-based extractor as a second module."""

    macosx = tmp_path / "__MACOSX"
    macosx.mkdir()
    (macosx / "._app.py").write_bytes(b"\x00\x05\x16\x07 not real python")
    (tmp_path / "._app.py").write_bytes(b"\x00\x05\x16\x07 not real python")
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    tree, meta, _ = RepositoryParser().parse(tmp_path, max_file_count=10)

    assert meta.total_files == 1
    assert [node.name for node in tree] == ["app.py"]


def test_repository_parser_file_count_preflight_ignores_macos_artifacts(tmp_path: Path):
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    (tmp_path / "._app.py").write_bytes(b"junk")
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    tree, meta, _ = RepositoryParser().parse(tmp_path, max_file_count=1)

    assert meta.total_files == 1


# --- symlink safety -----------------------------------------------------------
#
# Archive uploads can't reach this: TAR extraction rejects symlink/link/device
# members before writing (storage/local.py), and zipfile.extractall() never
# materializes a real OS symlink from a zip entry (confirmed empirically: it
# writes the "target" as literal file content instead). A GitHub import has no
# such guard -- git clone faithfully recreates whatever real symlinks the
# source repository committed. Path.is_dir()/is_file()/stat() (and
# os.DirEntry.is_dir()/is_file()) all follow symlinks by default, so an
# unguarded parser walking a git checkout would recurse into and catalog
# arbitrary host filesystem content reachable through a symlink that points
# outside the checkout.
#
# The parser therefore never follows a symlink. It records the path and steps
# over it, which keeps the escape unreachable while leaving the rest of the
# repository importable -- symlinks are ordinary in real repositories (TLS
# test fixtures, monorepo package links), and one of them should not cost the
# reader the other few hundred files.


def test_repository_parser_does_not_follow_a_symlink_that_escapes_the_checkout(tmp_path: Path):
    """The escape stays unreachable: nothing the link points at is catalogued."""

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "README.md").write_text("hello\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("host file content that must never be reachable\n", encoding="utf-8")
    (checkout / "evil_link").symlink_to(outside)

    tree, meta, _ = RepositoryParser().parse(checkout)

    paths = _all_paths(tree)
    assert "/evil_link" not in paths
    assert not any("secret.txt" in path for path in paths), "host content leaked through a symlink"
    assert paths == ["/README.md"]
    # Recorded, so the omission is visible rather than silent.
    assert meta.skipped_symlinks == ["/evil_link"]


def test_repository_parser_imports_the_rest_of_a_repository_containing_a_symlink(tmp_path: Path):
    """A symlink is an omission, not a reason to refuse the whole repository.

    This is the psf/requests case: one link under tests/certs/ used to reject
    a 100+ file repository outright.
    """

    checkout = tmp_path / "checkout"
    (checkout / "src").mkdir(parents=True)
    (checkout / "README.md").write_text("# demo\n", encoding="utf-8")
    (checkout / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (checkout / "src" / "linked.py").symlink_to(checkout / "src" / "app.py")

    tree, meta, _ = RepositoryParser().parse(checkout)

    paths = _all_paths(tree)
    assert "/README.md" in paths
    assert "/src/app.py" in paths
    # The link itself is not a second copy of the file it points at.
    assert "/src/linked.py" not in paths
    assert meta.skipped_symlinks == ["/src/linked.py"]
    assert meta.total_files == 2


def test_repository_parser_file_count_preflight_also_steps_over_a_symlink(tmp_path: Path):
    """The same escape via the separate max_file_count preflight scan.

    _enforce_file_count streams the tree with os.scandir before _build_tree
    ever runs, as its own independent walk -- it needs its own guard, not just
    _build_tree's, or a request with max_file_count set would still follow the
    link. A skipped link also counts for nothing against the budget.
    """

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "README.md").write_text("hello\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    for index in range(5):
        (outside / f"secret{index}.txt").write_text("marker\n", encoding="utf-8")
    (checkout / "evil_link").symlink_to(outside)

    _, meta, _ = RepositoryParser().parse(checkout, max_file_count=2)

    assert meta.total_files == 1
    assert meta.skipped_symlinks == ["/evil_link"]


def _all_paths(tree) -> list[str]:
    paths: list[str] = []

    def walk(nodes) -> None:
        for node in nodes:
            if node.type == "file":
                paths.append(node.path)
            walk(node.children or [])

    walk(tree)
    return sorted(paths)
