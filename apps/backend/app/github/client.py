import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, TimeoutServiceError, ValidationServiceError

logger = logging.getLogger(__name__)

GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?(?:\.git)?$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self.timeout_seconds = settings.clone_timeout_seconds
        self.max_clone_size_bytes = settings.max_clone_size_bytes

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

    def read_head_commit(self, repo_dir: Path) -> str | None:
        """Return the cloned repository's HEAD commit SHA, or None if unavailable."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_dir),
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            logger.warning("Unable to read HEAD commit for clone at %s: %s", repo_dir, exc)
            return None
        sha = result.stdout.strip()
        return sha or None

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
            # Keep raw git stderr (may contain local paths/URLs) server-side only.
            logger.warning("git clone failed for %s: %s", url, stderr)
            raise ExternalServiceError(
                "Failed to clone GitHub repository. Confirm the repository is public and the branch exists.",
            ) from exc

        self._enforce_clone_size(destination)

    def _enforce_clone_size(self, destination: Path) -> None:
        total = self._directory_size(destination)
        if total > self.max_clone_size_bytes:
            shutil.rmtree(destination, ignore_errors=True)
            raise ValidationServiceError(
                "Cloned repository exceeds the configured maximum size.",
                {"maxCloneSizeBytes": self.max_clone_size_bytes},
            )

    def _directory_size(self, path: Path) -> int:
        total = 0
        for child in path.rglob("*"):
            try:
                if child.is_file() and not child.is_symlink():
                    total += child.stat().st_size
            except OSError:
                continue
        return total
