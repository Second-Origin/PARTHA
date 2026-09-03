import asyncio
import io
import zipfile
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.core.config import get_settings
from app.storage.local import LocalStorage


class _FakeUpload:
    """Minimal UploadFile-like object with an attacker-controlled filename."""

    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self._buffer = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)


@pytest.fixture()
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalStorage:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    get_settings.cache_clear()
    try:
        yield LocalStorage(get_settings())
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "filename",
    [
        "../../evil.py",
        "../../../etc/passwd",
        "a/b/c.py",
        "..\\..\\evil.zip",
        "/abs/path/evil.tar.gz",
    ],
)
def test_save_upload_never_escapes_or_nests_uploads_dir(storage: LocalStorage, filename: str) -> None:
    upload = UploadFile(filename=filename, file=io.BytesIO(b"payload"))
    saved = asyncio.run(storage.save_upload("11111111-1111-1111-1111-111111111111", upload, 1024))

    resolved = saved.resolve()
    uploads_root = storage.uploads_root.resolve()
    # The stored file must be a direct child of uploads_root — no traversal, no nesting.
    assert resolved.parent == uploads_root
    assert resolved.name.startswith("11111111-1111-1111-1111-111111111111")
    # No path separators from the client filename survive into the stored name.
    assert "/" not in resolved.name and "\\" not in resolved.name


def test_save_upload_preserves_only_allowlisted_suffix(storage: LocalStorage) -> None:
    upload = UploadFile(filename="whatever.tar.gz", file=io.BytesIO(b"payload"))
    saved = asyncio.run(storage.save_upload("22222222-2222-2222-2222-222222222222", upload, 1024))
    assert saved.name == "22222222-2222-2222-2222-222222222222.tar.gz"


def test_extract_archive_strips_macos_finder_artifacts(storage: LocalStorage, tmp_path: Path) -> None:
    """#398: a zip made by macOS Finder's "Compress" carries __MACOSX/ plus a
    ._<name> AppleDouble sidecar per real file, and Finder itself may drop a
    .DS_Store into any directory -- none of it is repository content, and it
    must not still be sitting in the extracted repository's storage tree."""

    archive_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("project/app.py", "print('ok')\n")
        archive.writestr("project/.DS_Store", "junk")
        archive.writestr("__MACOSX/project/._app.py", "\x00\x05\x16\x07 resource fork")
        archive.writestr("project/._app.py", "\x00\x05\x16\x07 resource fork")

    root = storage.extract_archive(archive_path, "33333333-3333-3333-3333-333333333333")

    remaining = sorted(path.name for path in root.rglob("*"))
    assert remaining == ["app.py"]

    unsafe = UploadFile(filename="whatever.py", file=io.BytesIO(b"payload"))
    saved_unsafe = asyncio.run(storage.save_upload("33333333-3333-3333-3333-333333333333", unsafe, 1024))
    assert saved_unsafe.name == "33333333-3333-3333-3333-333333333333"
