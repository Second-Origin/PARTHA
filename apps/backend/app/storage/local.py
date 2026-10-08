import shutil
import struct
import tarfile
import zipfile
from pathlib import Path
from typing import cast

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import ValidationServiceError
from app.parsers.repository_parser import is_macos_artifact


class _BoundedTarInfo(tarfile.TarInfo):
    """Bound PAX/GNU metadata before CPython buffers extended header bodies."""

    MAX_METADATA_BYTES = 16 * 1024 * 1024

    def _proc_member(self, archive: tarfile.TarFile) -> tarfile.TarInfo | None:
        if self.type in {tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK}:
            consumed = getattr(archive, "_partha_metadata_bytes", 0) + self.size
            if self.size < 0 or consumed > self.MAX_METADATA_BYTES:
                raise ValidationServiceError("TAR extended metadata exceeds the supported ingestion limit.")
            setattr(archive, "_partha_metadata_bytes", consumed)
        # CPython private parser seam, exercised on supported Python versions.
        return cast(tarfile.TarInfo | None, getattr(tarfile.TarInfo, "_proc_member")(self, archive))


class LocalStorage:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.storage_path
        self.repositories_root = self.root / "repositories"
        self.uploads_root = self.root / "uploads"
        self.repositories_root.mkdir(parents=True, exist_ok=True)
        self.uploads_root.mkdir(parents=True, exist_ok=True)
        # Bound decompressed size and member count while iterating archive
        # members during extraction (see _safe_extract_zip/_safe_extract_tar),
        # so a zip/tar-bomb is rejected before it is ever written to disk.
        self.max_extracted_size_bytes = settings.max_extracted_size_bytes
        self.max_extracted_entries = settings.max_extracted_entries

    def repository_path(self, repository_id: str) -> Path:
        return self.repositories_root / repository_id

    def reset_repository_path(self, repository_id: str) -> Path:
        path = self.repository_path(repository_id)
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def delete_repository(self, local_path: str) -> None:
        path = Path(local_path)
        if path.exists() and path.is_dir():
            shutil.rmtree(path)

    def delete_repository_id(self, repository_id: str) -> None:
        path = self.repository_path(repository_id)
        if path.exists() and path.is_dir():
            shutil.rmtree(path)

    def delete_upload(self, archive_path: Path) -> None:
        archive_path.unlink(missing_ok=True)

    async def save_upload(self, repository_id: str, file: UploadFile, max_size_bytes: int) -> Path:
        # Never build the stored path from the client-supplied filename: derive it
        # solely from the server-generated UUID plus a validated archive suffix.
        upload_path = self.uploads_root / f"{repository_id}{self._safe_archive_suffix(file.filename)}"
        total = 0
        with upload_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_size_bytes:
                    upload_path.unlink(missing_ok=True)
                    raise ValidationServiceError("Upload exceeds configured maximum size.")
                destination.write(chunk)
        return upload_path

    SAFE_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar", ".zip", ".gz")

    def _safe_archive_suffix(self, filename: str | None) -> str:
        """Return an allowlisted archive suffix from a client filename, or "".

        The suffix is used only as a cosmetic hint on the stored file; archive
        type detection is content-based (see extract_archive), so an empty
        suffix is safe. No path separators or traversal can survive this.
        """
        if not filename:
            return ""
        lowered = filename.lower()
        for suffix in self.SAFE_ARCHIVE_SUFFIXES:
            if lowered.endswith(suffix):
                return suffix
        return ""

    def extract_archive(self, archive_path: Path, repository_id: str) -> Path:
        destination = self.reset_repository_path(repository_id)
        try:
            if zipfile.is_zipfile(archive_path):
                self._check_zip_metadata(archive_path)
                with zipfile.ZipFile(archive_path) as archive:
                    self._safe_extract_zip(archive, destination)
                self._strip_macos_artifacts(destination)
                return self._normalise_single_root(destination)

            # is_tarfile() parses the first member before our metadata guard.
            # Detect and extract in one bounded stream instead.
            try:
                tar_archive = tarfile.open(archive_path, mode="r|*", tarinfo=_BoundedTarInfo)
            except tarfile.ReadError as exc:
                raise ValidationServiceError("Unsupported archive format. Upload a ZIP or TAR archive.") from exc
            with tar_archive:
                self._safe_extract_tar(tar_archive, destination)
            self._strip_macos_artifacts(destination)
            return self._normalise_single_root(destination)
        except (zipfile.BadZipFile, tarfile.TarError, OSError) as exc:
            raise ValidationServiceError("Archive is corrupted or cannot be extracted.") from exc

        raise ValidationServiceError("Unsupported archive format. Upload a ZIP or TAR archive.")

    def _check_zip_metadata(self, path: Path) -> None:
        """Bound central-directory work before ZipFile creates ZipInfo objects.

        CPython's bounded footer reader supports ordinary and ZIP64 end records.
        Count actual central headers too: ZipFile does not trust footer counts.
        The private footer constants mirror our supported Python 3.12/3.13
        ZipFile implementation; regression fixtures exercise this boundary.
        """
        with path.open("rb") as source:
            footer = getattr(zipfile, "_EndRecData")(source)
            if footer is None:
                raise zipfile.BadZipFile("Missing end record")
            size = footer[getattr(zipfile, "_ECD_SIZE")]
            if footer[getattr(zipfile, "_ECD_ENTRIES_TOTAL")] > self.max_extracted_entries:
                raise ValidationServiceError("Archive contains more entries than the configured maximum.")
            if size > 16 * 1024 * 1024:
                raise ValidationServiceError("Archive central-directory metadata exceeds configured limits.")
            start = footer[getattr(zipfile, "_ECD_LOCATION")] - size
            if footer[getattr(zipfile, "_ECD_SIGNATURE")] == getattr(zipfile, "stringEndArchive64"):
                start -= getattr(zipfile, "sizeEndCentDir64") + getattr(zipfile, "sizeEndCentDir64Locator")
            if size < 0 or start < 0:
                raise zipfile.BadZipFile("Invalid central-directory bounds")
            source.seek(start)
            end = start + size
            count = 0
            while source.tell() < end:
                raw = source.read(getattr(zipfile, "sizeCentralDir"))
                if len(raw) != getattr(zipfile, "sizeCentralDir"):
                    raise zipfile.BadZipFile("Truncated central-directory header")
                header = struct.unpack(getattr(zipfile, "structCentralDir"), raw)
                if header[0] != getattr(zipfile, "stringCentralDir"):
                    raise zipfile.BadZipFile("Invalid central-directory header")
                count += 1
                if count > self.max_extracted_entries:
                    raise ValidationServiceError("Archive contains more entries than the configured maximum.")
                length = sum(
                    header[index]
                    for index in (
                        getattr(zipfile, "_CD_FILENAME_LENGTH"),
                        getattr(zipfile, "_CD_EXTRA_FIELD_LENGTH"),
                        getattr(zipfile, "_CD_COMMENT_LENGTH"),
                    )
                )
                if source.tell() + length > end:
                    raise zipfile.BadZipFile("Invalid central-directory member bounds")
                source.seek(length, 1)

    def _safe_extract_zip(self, archive: zipfile.ZipFile, destination: Path) -> None:
        total_size = 0
        for entry_index, member in enumerate(archive.infolist(), start=1):
            target = destination / member.filename
            if not self._is_safe_child(destination, target):
                raise ValidationServiceError("Archive contains unsafe paths.")
            if entry_index > self.max_extracted_entries:
                raise ValidationServiceError(
                    "Archive contains more entries than the configured maximum.",
                    {"maxExtractedEntries": self.max_extracted_entries},
                )
            # ZipInfo.file_size is the member's declared decompressed size, so
            # this rejects an oversized member using its own metadata, before
            # any of its bytes are written to disk.
            total_size += member.file_size
            if total_size > self.max_extracted_size_bytes:
                raise ValidationServiceError(
                    "Archive would decompress to more than the configured maximum size.",
                    {"maxExtractedSizeBytes": self.max_extracted_size_bytes},
                )
        archive.extractall(destination)

    def _safe_extract_tar(self, archive: tarfile.TarFile, destination: Path) -> None:
        total_size = 0
        for entry_index, member in enumerate(archive, start=1):
            if member.issym() or member.islnk() or member.isdev():
                raise ValidationServiceError("Archive contains unsupported link or device entries.")
            target = destination / member.name
            if not self._is_safe_child(destination, target):
                raise ValidationServiceError("Archive contains unsafe paths.")
            if entry_index > self.max_extracted_entries:
                raise ValidationServiceError(
                    "Archive contains more entries than the configured maximum.",
                    {"maxExtractedEntries": self.max_extracted_entries},
                )
            # TarInfo.size is the member's declared decompressed size, checked
            # the same way as the zip path above: reject before extraction.
            total_size += member.size
            if total_size > self.max_extracted_size_bytes:
                raise ValidationServiceError(
                    "Archive would decompress to more than the configured maximum size.",
                    {"maxExtractedSizeBytes": self.max_extracted_size_bytes},
                )
            # `filter="data"` applies CPython's own extraction hardening: it strips
            # absolute paths and `..` traversal, and rejects links, devices, setuid
            # bits and other unsafe metadata as the members are written.
            #
            # The loop above already rejects those cases, so this is defence in
            # depth on untrusted uploads rather than the primary control — the two
            # have to disagree for it to matter, which is exactly when a check is
            # worth having. It also settles the DeprecationWarning: tar extraction
            # is unfiltered by default until Python 3.14, which would switch this
            # behaviour on silently. Being explicit keeps it a decision.
            archive.extract(member, destination, filter="data")
            getattr(archive, "members").clear()

    def _strip_macos_artifacts(self, destination: Path) -> None:
        """Delete Finder/Archive Utility artifacts an archive may carry (#397).

        RepositoryParser already excludes these from the persisted file tree
        (so they never reach the extraction pipeline or the UI), but that
        leaves them sitting on disk in the repository's own storage tree.
        Removing them here too keeps that tree honest, not just what's
        derived from it.
        """

        if destination.name == "__MACOSX" or is_macos_artifact(destination.name):
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
            return
        if not destination.is_dir():
            return
        for child in list(destination.iterdir()):
            self._strip_macos_artifacts(child)

    def _normalise_single_root(self, destination: Path) -> Path:
        children = list(destination.iterdir())
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return destination

    def _is_safe_child(self, root: Path, target: Path) -> bool:
        try:
            target.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False
