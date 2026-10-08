import tarfile
import zipfile

import pytest
from app.core.config import Settings
from app.core.exceptions import ValidationServiceError
from app.storage.local import LocalStorage


def test_zip_count_rejected_before_zipinfo_materialization(tmp_path, monkeypatch):
    path = tmp_path / "many.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for index in range(5):
            archive.writestr(f"{index}.txt", "")
    storage = LocalStorage(Settings(storage_path=tmp_path / "storage", max_extracted_entries=3))

    def forbidden(*args, **kwargs):
        raise AssertionError("ZipInfo materialized before metadata limit")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden)
    with pytest.raises(ValidationServiceError, match="Archive contains more entries than the configured maximum"):
        storage.extract_archive(path, "bounded")


def test_tar_count_is_checked_without_getmembers(tmp_path, monkeypatch):
    path = tmp_path / "many.tar"
    with tarfile.open(path, "w") as archive:
        for index in range(5):
            archive.addfile(tarfile.TarInfo(f"{index}.txt"))
    storage = LocalStorage(Settings(storage_path=tmp_path / "storage", max_extracted_entries=3))

    def forbidden(*args, **kwargs):
        raise AssertionError("TAR fully enumerated")

    monkeypatch.setattr(tarfile.TarFile, "getmembers", forbidden)
    with pytest.raises(ValidationServiceError, match="more entries"):
        storage.extract_archive(path, "bounded")


def test_small_force_zip64_archive_still_extracts(tmp_path):
    path = tmp_path / "small.zip"
    with zipfile.ZipFile(path, "w") as archive:
        with archive.open("small.txt", "w", force_zip64=True) as member:
            member.write(b"valid")
    storage = LocalStorage(Settings(storage_path=tmp_path / "storage"))
    destination = storage.extract_archive(path, "bounded")
    assert (destination / "small.txt").read_bytes() == b"valid"


def test_tar_extended_metadata_rejected_before_buffering(tmp_path, monkeypatch):
    from app.storage.local import _BoundedTarInfo

    path = tmp_path / "header-only.tar"
    header = tarfile.TarInfo("extended")
    header.type = tarfile.XHDTYPE
    header.size = 2048
    path.write_bytes(header.tobuf())
    monkeypatch.setattr(_BoundedTarInfo, "MAX_METADATA_BYTES", 1024)

    def forbidden(*args, **kwargs):
        raise AssertionError("PAX metadata body buffered before limit")

    monkeypatch.setattr(tarfile.TarInfo, "_proc_pax", forbidden)
    storage = LocalStorage(Settings(storage_path=tmp_path / "storage"))
    with pytest.raises(ValidationServiceError, match="extended metadata"):
        storage.extract_archive(path, "bounded")


def test_valid_pax_metadata_still_extracts(tmp_path):
    path = tmp_path / "valid-pax.tar"
    with tarfile.open(path, "w", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo("small.txt")
        info.pax_headers = {"comment": "valid extended metadata"}
        archive.addfile(info)
    storage = LocalStorage(Settings(storage_path=tmp_path / "storage"))
    assert (storage.extract_archive(path, "bounded") / "small.txt").is_file()
