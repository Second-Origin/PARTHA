import os
import re
import shutil
import subprocess
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, TimeoutServiceError, ValidationServiceError

GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?(?:\.git)?$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


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

    def validate_branch(self, branch: str | None) -> str | None:
        if not branch:
            return None
        if (
            not BRANCH_RE.match(branch)
            or ".." in branch
            or branch.startswith(("/", "-"))
            or branch.endswith(("/", "."))
        ):
            raise ValidationServiceError("Branch name contains unsupported characters.")
        return branch

    def repository_name(self, url: str) -> str:
        return url.rstrip("/").split("/")[-1].removesuffix(".git")

    def clone_public_repository(self, url: str, destination: Path, branch: str | None = None) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        command = ["git", "clone", "--depth=1", "--single-branch"]
        if branch:
            command.extend(["--branch", branch])
        command.extend([url, str(destination)])
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(destination, ignore_errors=True)
            raise TimeoutServiceError(
                "GitHub repository clone timed out.",
                {"timeoutSeconds": self.timeout_seconds},
            ) from exc
        except (subprocess.CalledProcessError, OSError) as exc:
            shutil.rmtree(destination, ignore_errors=True)
            stderr = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            raise ExternalServiceError(
                "Failed to clone GitHub repository. Confirm the repository is public and the branch exists.",
                {"stderr": stderr},
            ) from exc
