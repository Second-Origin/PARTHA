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
            logger.warning("Unable to read HEAD commit for cloned repository (%s).", type(exc).__name__)
            return None
        sha = result.stdout.strip()
        return sha or None

    def read_head_ref(self, repo_dir: Path, requested_ref: str | None = None) -> str | None:
        """Return the resolved ref HEAD points at (e.g. ``refs/heads/main``).

        Recorded alongside the commit SHA as descriptive revision metadata
        (RFC §3.2); it is a moving pointer and never revision identity. A
        detached tag clone is resolved only after git confirms the requested tag
        points at HEAD. Returns ``None`` when git cannot answer unambiguously.
        """
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "HEAD"],
                cwd=str(repo_dir),
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (subprocess.SubprocessError, OSError):
            # A tag clone has detached HEAD. Confirm the requested name against
            # refs instead of fabricating a refs/heads value from user input.
            if requested_ref:
                for candidate, normalized in (
                    (f"refs/heads/{requested_ref}", f"refs/heads/{requested_ref}"),
                    (f"refs/tags/{requested_ref}", f"refs/tags/{requested_ref}"),
                    (f"refs/remotes/origin/{requested_ref}", f"refs/heads/{requested_ref}"),
                ):
                    try:
                        resolved = subprocess.run(
                            ["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"],
                            cwd=str(repo_dir),
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=self.timeout_seconds,
                        ).stdout.strip()
                        head = subprocess.run(
                            ["git", "rev-parse", "HEAD"],
                            cwd=str(repo_dir),
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=self.timeout_seconds,
                        ).stdout.strip()
                    except (subprocess.SubprocessError, OSError):
                        continue
                    if resolved and resolved == head:
                        return normalized
            logger.warning("Unable to resolve HEAD to a normalized Git ref for cloned repository.")
            return None
        ref = result.stdout.strip()
        return ref if ref.startswith("refs/") else None

    def read_remote_head_commit(self, url: str, branch: str | None = None) -> str | None:
        """Resolve a branch head over the network without cloning (#448).

        Re-analysis asks "has this moved?", and for a repository that has not
        moved -- the common answer -- a full clone is a download, a parse and a
        directory of disk to learn one SHA. ``ls-remote`` answers the same
        question in one round trip and touches no storage.

        ``url`` and ``branch`` must already be through ``validate_public_url``
        and ``validate_branch``: both are passed to git as arguments, and the
        branch is additionally wrapped as a full ``refs/heads/`` ref so a name
        can never be read as a flag or a wildcard.
        """

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        ref = f"refs/heads/{branch}" if branch else "HEAD"
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--exit-code", "--", url, ref],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutServiceError(
                "Resolving the GitHub branch head timed out.",
                {"timeoutSeconds": self.timeout_seconds},
            ) from exc
        except (subprocess.CalledProcessError, OSError) as exc:
            return_code = exc.returncode if isinstance(exc, subprocess.CalledProcessError) else None
            # As with clone, raw stderr is not logged: it can echo the URL and
            # whatever the remote chose to say back.
            logger.warning(
                "git ls-remote failed for public repository (error_type=%s, return_code=%s).",
                type(exc).__name__,
                return_code,
            )
            raise ExternalServiceError(
                "Failed to reach the GitHub repository. Confirm it is still public and the branch still exists.",
            ) from exc

        first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        sha = first_line.split("\t", 1)[0].strip() if first_line else ""
        # A short or non-hex answer means the remote said something this method
        # does not understand; reporting None keeps the caller from comparing a
        # malformed value against a sealed revision.
        if len(sha) != 40 or not all(character in "0123456789abcdef" for character in sha):
            return None
        return sha

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
            return_code = exc.returncode if isinstance(exc, subprocess.CalledProcessError) else None
            # Raw stderr can contain the destination's absolute host path and is
            # intentionally not logged.
            logger.warning(
                "git clone failed for public repository (error_type=%s, return_code=%s).",
                type(exc).__name__,
                return_code,
            )
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
        for root, dirs, files in os.walk(path, followlinks=False):
            for name in files:
                child = Path(root, name)
                try:
                    if not child.is_symlink():
                        total += child.stat().st_size
                except OSError:
                    continue
            # Do not descend into symlinked directories: prevents a crafted
            # symlink (e.g. to / or a parent dir) from causing disclosure or a
            # size-measurement loop during clone budget enforcement.
            dirs[:] = [d for d in dirs if not Path(root, d).is_symlink()]
        return total
