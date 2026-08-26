from pathlib import Path

import pytest

import app.parsers.repository_parser as repository_parser_module
from app.parsers.repository_parser import RepositoryFileLimitExceeded, RepositoryParser, UnsafeRepositoryPath


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


def test_repository_parser_rejects_a_symlink_that_escapes_the_checkout(tmp_path: Path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "README.md").write_text("hello\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("host file content that must never be reachable\n", encoding="utf-8")
    (checkout / "evil_link").symlink_to(outside)

    with pytest.raises(UnsafeRepositoryPath) as caught:
        RepositoryParser().parse(checkout)

    assert caught.value.relative_path == "/evil_link"


def test_repository_parser_file_count_preflight_also_rejects_a_symlink(tmp_path: Path):
    """The same escape via the separate max_file_count preflight scan.

    _enforce_file_count streams the tree with os.scandir before _build_tree
    ever runs, as its own independent walk -- it needed its own guard, not
    just _build_tree's, or a request with max_file_count set would still be
    exploitable.
    """

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("marker\n", encoding="utf-8")
    (checkout / "evil_link").symlink_to(outside)

    with pytest.raises(UnsafeRepositoryPath):
        RepositoryParser().parse(checkout, max_file_count=1000)


def test_repository_parser_rejects_a_symlink_even_when_it_resolves_inside_the_checkout(tmp_path: Path):
    """Deliberately as strict as the archive-upload path: any symlink at all.

    A symlink that points at a file within the same checkout can't be used to
    reach host content, but the file tree walk rejects it anyway rather than
    trying to special-case "safe" symlinks -- matching the existing TAR
    extraction policy (reject any symlink member, full stop) rather than
    inventing a second, more permissive policy for this path.
    """

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "real.py").write_text("value = 1\n", encoding="utf-8")
    (checkout / "alias.py").symlink_to(checkout / "real.py")

    with pytest.raises(UnsafeRepositoryPath):
        RepositoryParser().parse(checkout)


def test_repository_parser_framework_detection_ignores_a_symlink_that_escapes_the_checkout(tmp_path: Path):
    """Defence in depth for the metadata-detection helpers specifically.

    In practice the file-tree walk above already rejects the whole import
    before _detect_framework ever runs, for any repository containing any
    symlink anywhere. This tests the helper in isolation anyway: unlike the
    tree walk, it reads file content by a fixed, predictable name
    (package.json), so if the tree-walk guard were ever loosened to skip
    rather than reject individual symlinks, this is the layer that stops a
    symlinked package.json from being read as JSON from an arbitrary host
    path.
    """

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"dependencies": {"react": "18.0.0"}}', encoding="utf-8")
    (checkout / "package.json").symlink_to(outside)

    assert RepositoryParser()._detect_framework(checkout) == "Unknown"


def test_repository_parser_framework_detection_still_works_through_an_in_root_symlink(tmp_path: Path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "real_package.json").write_text('{"dependencies": {"react": "18.0.0"}}', encoding="utf-8")
    (checkout / "package.json").symlink_to(checkout / "real_package.json")

    assert RepositoryParser()._detect_framework(checkout) == "React"


def test_repository_parser_license_detection_ignores_a_symlink_that_escapes_the_checkout(tmp_path: Path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = tmp_path / "outside_license.txt"
    outside.write_text("MIT License\n", encoding="utf-8")
    (checkout / "LICENSE").symlink_to(outside)

    assert RepositoryParser()._detect_license(checkout) is None
