import os
import re
from pathlib import Path

from git import GitCommandError, Repo

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, ValidationServiceError

GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?(?:\.git)?$")


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self.timeout_seconds = settings.clone_timeout_seconds

    def validate_public_url(self, url: str) -> str:
        normalized = url.rstrip("/")
        if normalized.endswith(".git"):
            normalized = normalized[:-4]
        if not GITHUB_RE.match(normalized):
            raise ValidationServiceError("Only public GitHub repository HTTPS URLs are supported.")
        return normalized

    def repository_name(self, url: str) -> str:
        return url.rstrip("/").split("/")[-1].removesuffix(".git")

    def clone_public_repository(self, url: str, destination: Path, branch: str | None = None) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        options = ["--depth=1"]
        try:
            Repo.clone_from(
                url,
                destination,
                branch=branch,
                multi_options=options,
                env=env,
            )
        except GitCommandError as exc:
            raise ExternalServiceError("Failed to clone GitHub repository.", {"stderr": str(exc)}) from exc
