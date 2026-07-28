"""Deterministic, symlink-safe streaming of a stored repository manifest."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path, PurePosixPath

from app.analysis.resource_budget import AnalysisResourceBudget
from app.intelligence import canonical


class UnsafeSourcePath(RuntimeError):
    """A stored manifest path no longer resolves to a safe regular file."""


class RepositorySourceStream:
    """Yield bounded source payloads one at a time from the persisted file tree."""

    def __init__(
        self,
        *,
        root: Path,
        file_tree: Sequence[object],
        max_file_bytes: int,
        budget: AnalysisResourceBudget,
        check_cancelled: Callable[[], None] | None = None,
    ) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be greater than zero")
        self.root = root.resolve(strict=True)
        self.manifest = file_tree
        self.max_file_bytes = max_file_bytes
        self.budget = budget
        self.check_cancelled = check_cancelled

    def __iter__(self) -> Iterator[tuple[str, bytes]]:
        for path in self._manifest_paths(self.manifest):
            self._checkpoint()
            candidate = self.root.joinpath(*PurePosixPath(path).parts)
            self._reject_symlink_components(candidate, path)
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(candidate, flags)
            except FileNotFoundError:
                # Preserve the existing policy for files removed after ingestion.
                continue
            except OSError as exc:
                raise UnsafeSourcePath(f"could not safely open stored source path {path!r}") from exc
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise UnsafeSourcePath(f"stored source path {path!r} is not a regular file")
                self.budget.charge_source(metadata.st_size)
                with os.fdopen(descriptor, "rb", closefd=True) as handle:
                    descriptor = -1
                    source = handle.read(self.max_file_bytes + 1)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
            self._checkpoint()
            yield path, source

    def _checkpoint(self) -> None:
        if self.check_cancelled is not None:
            self.check_cancelled()
        self.budget.check()

    def _reject_symlink_components(self, candidate: Path, path: str) -> None:
        current = self.root
        for component in candidate.relative_to(self.root).parts:
            current /= component
            try:
                is_junction = getattr(current, "is_junction", lambda: False)()
                if current.is_symlink() or is_junction:
                    raise UnsafeSourcePath(f"stored source path {path!r} traverses a symlink")
            except OSError as exc:
                raise UnsafeSourcePath(f"could not validate stored source path {path!r}") from exc

    @classmethod
    def _manifest_paths(cls, nodes: Sequence[object]) -> tuple[str, ...]:
        normalized: set[str] = set()
        for raw_path in cls._iter_file_paths(nodes):
            # Persisted file-tree paths use one leading slash as a repository
            # root marker. It is not a host-filesystem absolute path.
            manifest_path = raw_path[1:] if raw_path.startswith("/") and not raw_path.startswith("//") else raw_path
            try:
                path = canonical.normalize_repo_path(manifest_path)
            except canonical.PathEscapeError as exc:
                raise UnsafeSourcePath(f"stored source path {raw_path!r} escapes the repository root") from exc
            if not path:
                raise UnsafeSourcePath("stored source path must not be empty")
            normalized.add(path)
        return tuple(sorted(normalized))

    @classmethod
    def _iter_file_paths(cls, nodes: Sequence[object]) -> Iterator[str]:
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            if node.get("type") == "file" and node.get("path"):
                yield str(node["path"])
            children = node.get("children")
            if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
                yield from cls._iter_file_paths(children)
