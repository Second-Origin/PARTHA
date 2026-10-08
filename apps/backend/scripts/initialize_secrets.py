"""Validate surviving secret files and atomically create only missing keys."""

import os
from pathlib import Path
import secrets
import tempfile

from cryptography.fernet import Fernet


def _validate(name: str, value: str) -> None:
    if name == "auth_secret_key":
        if len(value.strip()) < 32:
            raise ValueError("Invalid existing auth_secret_key: requires at least 32 characters.")
    else:
        try:
            Fernet(value.strip().encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Invalid existing ai_encryption_key: requires a Fernet key.") from exc


def initialize(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    names = ("auth_secret_key", "ai_encryption_key")
    # Validate every survivor before creating anything. Never overwrite a
    # corrupt survivor or silently rotate the other key to repair it.
    for name in names:
        path = directory / name
        if path.exists():
            _validate(name, path.read_text(encoding="utf-8"))
    for name in names:
        path = directory / name
        if path.exists():
            continue
        value = secrets.token_urlsafe(48) if name == "auth_secret_key" else Fernet.generate_key().decode("ascii")
        fd, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(value)
                file.flush()
                os.fsync(file.fileno())
            try:
                # Link a complete file into place exclusively. A concurrent
                # initializer cannot replace an already published secret.
                os.link(temporary, path)
            except FileExistsError:
                _validate(name, path.read_text(encoding="utf-8"))
        finally:
            Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    initialize(Path(os.environ["SECRETS_DIR"]))
