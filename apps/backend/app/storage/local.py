import shutil
import tarfile
import zipfile
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import ValidationServiceError


class LocalStorage:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.storage_path
        self.repositories_root = self.root / "repositories"
        self.uploads_root = self.root / "uploads"
        self.repositories_root.mkdir(parents=True, exist_ok=True)
        self.uploads_root.mkdir(parents=True, exist_ok=True)

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

    async def save_upload(self, repository_id: str, file: UploadFile, max_size_bytes: int) -> Path:
        upload_path = self.uploads_root / f"{repository_id}-{file.filename or 'repository'}"
        total = 0
        with upload_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_size_bytes:
                    upload_path.unlink(missing_ok=True)
                    raise ValidationServiceError("Upload exceeds configured maximum size.")
                destination.write(chunk)
        return upload_path

    def extract_archive(self, archive_path: Path, repository_id: str) -> Path:
        destination = self.reset_repository_path(repository_id)
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path) as archive:
                self._safe_extract_zip(archive, destination)
            return self._normalise_single_root(destination)

        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path) as archive:
                self._safe_extract_tar(archive, destination)
            return self._normalise_single_root(destination)

        raise ValidationServiceError("Unsupported archive format. Upload a ZIP or TAR archive.")

    def _safe_extract_zip(self, archive: zipfile.ZipFile, destination: Path) -> None:
        for member in archive.infolist():
            target = destination / member.filename
            if not self._is_safe_child(destination, target):
                raise ValidationServiceError("Archive contains unsafe paths.")
        archive.extractall(destination)

    def _safe_extract_tar(self, archive: tarfile.TarFile, destination: Path) -> None:
        for member in archive.getmembers():
            target = destination / member.name
            if not self._is_safe_child(destination, target):
                raise ValidationServiceError("Archive contains unsafe paths.")
        archive.extractall(destination)

    def _normalise_single_root(self, destination: Path) -> Path:
        children = [child for child in destination.iterdir() if child.name != "__MACOSX"]
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return destination

    def _is_safe_child(self, root: Path, target: Path) -> bool:
        try:
            target.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False
