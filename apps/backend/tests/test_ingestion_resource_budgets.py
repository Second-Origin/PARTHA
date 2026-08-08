"""Resource-budget enforcement during archive extraction and repository ingestion.

`LocalStorage.extract_archive` bounds nothing about decompressed size or
entry count while iterating zip/tar members, and neither ingestion path
(`RepositoryService.import_github_repository` /
`RepositoryService.import_uploaded_repository`) bounds the total number of
files a repository resolves to. These tests exercise the new
`max_extracted_size_bytes` / `max_extracted_entries` / `max_file_count`
budgets end to end through the API, with the relevant setting lowered via
environment variables (never real gigabyte-scale payloads) so the checks
trip on small, fast fixtures.
"""

import io
import os
import tarfile
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api_assertions import assert_error_response
from tests.conftest import register_user


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _tar_gz_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(path)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _upload(client: TestClient, filename: str, content: bytes):
    return client.post(
        "/repositories/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )


def _repositories_dir_is_empty(storage_path: Path) -> bool:
    repositories_dir = storage_path / "repositories"
    if not repositories_dir.exists():
        return True
    return not any(repositories_dir.iterdir())


def _build_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra_env: dict[str, str]
) -> Generator[TestClient, None, None]:
    """The standard ``client`` fixture body, with one ingestion budget lowered.

    Mirrors ``tests.conftest.client`` / ``tests.test_rate_limit.limited_client``:
    the relevant setting is set via environment variable *before*
    ``create_app()`` builds the dependency graph, since ``Settings`` is only
    ever constructed from the environment (see ``app/core/config.py``).
    """
    database_path = tmp_path / "partha-test.db"
    storage_path = tmp_path / "storage"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_PATH", str(storage_path))
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    for key, value in extra_env.items():
        monkeypatch.setenv(key, value)

    from app.core import config

    config.get_settings.cache_clear()

    import app.core.database as database

    settings = config.get_settings()
    database.settings = settings
    database.engine.dispose()
    database.connect_args = {"check_same_thread": False}
    database.engine = database.create_engine(
        settings.database_url, pool_pre_ping=True, connect_args=database.connect_args
    )
    database.SessionLocal.configure(bind=database.engine)

    from app.core.schema_sync import stamp_head
    from app.main import create_app
    from app.models.base import Base

    Base.metadata.create_all(bind=database.engine)
    # Mirrors what the app's own lifespan does for a genuinely fresh database
    # (#166); see the identical comment in tests/conftest.py.
    stamp_head(database.engine)
    with TestClient(create_app()) as test_client:
        auth = register_user(test_client, "budget@example.com")
        test_client.headers.update(auth["headers"])
        test_client.storage_path = storage_path  # type: ignore[attr-defined]
        yield test_client

    for key in ("DATABASE_URL", "STORAGE_PATH", "AUTO_CREATE_TABLES", "CORS_ORIGINS", *extra_env):
        os.environ.pop(key, None)
    config.get_settings.cache_clear()


@pytest.fixture()
def size_limited_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """``max_extracted_size_bytes`` lowered to 1KiB; other budgets stay generous."""
    yield from _build_client(tmp_path, monkeypatch, {"MAX_EXTRACTED_SIZE_BYTES": "1024"})


@pytest.fixture()
def entries_limited_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """``max_extracted_entries`` lowered to 5; other budgets stay generous."""
    yield from _build_client(tmp_path, monkeypatch, {"MAX_EXTRACTED_ENTRIES": "5"})


@pytest.fixture()
def file_count_limited_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """``max_file_count`` lowered to 5; other budgets stay generous."""
    yield from _build_client(tmp_path, monkeypatch, {"MAX_FILE_COUNT": "5"})


# --- extracted-size budget -------------------------------------------------


def test_zip_archive_over_extracted_size_limit_is_rejected_and_cleaned_up(size_limited_client: TestClient):
    response = _upload(
        size_limited_client,
        "bomb.zip",
        # A single member whose real (decompressed) size exceeds the 1KiB cap.
        # zipfile.ZipInfo.file_size always reflects the actual data length, so
        # this is a genuine oversized member, not a spoofed one.
        _zip_bytes({"bomb/payload.bin": "x" * 4096}),
    )

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive would decompress to more than the configured maximum size."
    assert _repositories_dir_is_empty(size_limited_client.storage_path)  # type: ignore[attr-defined]


def test_tar_archive_over_extracted_size_limit_is_rejected_and_cleaned_up(size_limited_client: TestClient):
    response = _upload(
        size_limited_client,
        "bomb.tar.gz",
        _tar_gz_bytes({"bomb/payload.bin": "x" * 4096}),
    )

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive would decompress to more than the configured maximum size."
    assert _repositories_dir_is_empty(size_limited_client.storage_path)  # type: ignore[attr-defined]


def test_many_small_members_summing_over_extracted_size_limit_is_rejected(size_limited_client: TestClient):
    # No single member is large, but the cumulative decompressed total is.
    files = {f"bomb/part{i}.bin": "x" * 200 for i in range(10)}  # 2000 bytes > 1024 cap
    response = _upload(size_limited_client, "many-parts.zip", _zip_bytes(files))

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive would decompress to more than the configured maximum size."
    assert _repositories_dir_is_empty(size_limited_client.storage_path)  # type: ignore[attr-defined]


# --- extracted-entry-count budget ------------------------------------------


def test_zip_archive_over_extracted_entries_limit_is_rejected_and_cleaned_up(entries_limited_client: TestClient):
    files = {f"many/file{i}.txt": "x" for i in range(10)}  # 10 entries > 5 cap
    response = _upload(entries_limited_client, "many-entries.zip", _zip_bytes(files))

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive contains more entries than the configured maximum."
    assert _repositories_dir_is_empty(entries_limited_client.storage_path)  # type: ignore[attr-defined]


def test_tar_archive_over_extracted_entries_limit_is_rejected_and_cleaned_up(entries_limited_client: TestClient):
    files = {f"many/file{i}.txt": "x" for i in range(10)}
    response = _upload(entries_limited_client, "many-entries.tar.gz", _tar_gz_bytes(files))

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive contains more entries than the configured maximum."
    assert _repositories_dir_is_empty(entries_limited_client.storage_path)  # type: ignore[attr-defined]


# --- repository-wide file-count budget --------------------------------------


def test_upload_with_file_tree_over_file_count_limit_is_rejected_and_cleaned_up(
    file_count_limited_client: TestClient,
):
    # 8 files > MAX_FILE_COUNT=5, but well inside the (default, generous)
    # extracted-size/entry-count budgets, so this exercises the
    # RepositoryService-level check specifically, not the archive-level ones.
    files = {f"project/file{i}.py": "print(1)\n" for i in range(8)}
    response = _upload(file_count_limited_client, "project.zip", _zip_bytes(files))

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Repository exceeds the configured maximum file count."
    assert error.details == {"maxFileCount": 5, "fileCount": 6}
    assert _repositories_dir_is_empty(file_count_limited_client.storage_path)  # type: ignore[attr-defined]


def test_github_import_with_file_tree_over_file_count_limit_is_rejected_and_cleaned_up(
    file_count_limited_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.github.client import GitHubClient

    def fake_clone(_: GitHubClient, __: str, destination: Path, ___: str | None = None) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for i in range(8):
            (destination / f"file{i}.py").write_text("print(1)\n", encoding="utf-8")

    monkeypatch.setattr(GitHubClient, "clone_public_repository", fake_clone)
    monkeypatch.setattr(GitHubClient, "read_head_commit", lambda *_: "a" * 40)
    monkeypatch.setattr(GitHubClient, "read_head_ref", lambda *_: "refs/heads/main")

    response = file_count_limited_client.post(
        "/repositories/github", json={"url": "https://github.com/example/demo"}
    )

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Repository exceeds the configured maximum file count."
    assert error.details == {"maxFileCount": 5, "fileCount": 6}
    assert _repositories_dir_is_empty(file_count_limited_client.storage_path)  # type: ignore[attr-defined]


# --- archive path safety ------------------------------------------------------
#
# These cover the guards in ``LocalStorage._safe_extract_tar`` /
# ``_safe_extract_zip`` that reject traversal and link members. They were
# previously untested, so a regression would have been silent — and the tar
# path additionally relies on ``extractall(filter="data")`` as defence in depth.


def _malicious_tar_gz_bytes(members: list[tarfile.TarInfo], payload: bytes = b"pwned") -> bytes:
    """A tar built from raw ``TarInfo`` objects, so unsafe members can be forged."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info in members:
            if info.isreg():
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            else:
                archive.addfile(info)
    return buffer.getvalue()


def test_tar_archive_with_parent_traversal_path_is_rejected(auth_client):
    """A member escaping the destination via ``..`` must never be written."""
    escaping = tarfile.TarInfo("../escaped.txt")
    escaping.type = tarfile.REGTYPE

    response = _upload(auth_client, "evil.tar.gz", _malicious_tar_gz_bytes([escaping]))

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive contains unsafe paths."


def test_tar_archive_with_absolute_path_is_rejected(auth_client):
    """An absolute member path must not be able to write outside the sandbox."""
    absolute = tarfile.TarInfo("/tmp/partha-escaped.txt")
    absolute.type = tarfile.REGTYPE

    response = _upload(auth_client, "evil.tar.gz", _malicious_tar_gz_bytes([absolute]))

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive contains unsafe paths."


def test_tar_archive_with_symlink_member_is_rejected(auth_client):
    """Symlinks are refused outright: they are the classic extraction escape."""
    link = tarfile.TarInfo("sample/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"

    response = _upload(auth_client, "evil.tar.gz", _malicious_tar_gz_bytes([link]))

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive contains unsupported link or device entries."


def test_zip_archive_with_parent_traversal_path_is_rejected(auth_client):
    """The zip path enforces the same containment rule as the tar path."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escaped.txt", "pwned")

    response = _upload(auth_client, "evil.zip", buffer.getvalue())

    error = assert_error_response(response, 422, "validation_error")
    assert error.message == "Archive contains unsafe paths."


# --- regression: unaffected happy path --------------------------------------


def test_small_normal_upload_still_succeeds_under_default_budgets(auth_client):
    response = _upload(
        auth_client,
        "sample.zip",
        _zip_bytes(
            {
                "sample/package.json": '{"dependencies":{"react":"^18.0.0"}}',
                "sample/src/main.tsx": "import React from 'react';",
                "sample/README.md": "# Sample",
            }
        ),
    )

    assert response.status_code == 201
    repository = response.json()
    assert repository["name"] == "sample"
    assert repository["status"] == "analysing"
