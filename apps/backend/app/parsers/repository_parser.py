import json
import os
from collections import Counter
from pathlib import Path
from uuid import uuid4

from app.schemas.repository import FileTreeNode, RepositoryMeta

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "vendor",
    "vendors",
    "generated",
    "__MACOSX",
}


def is_macos_artifact(name: str) -> bool:
    """True for a macOS Finder/Archive Utility artifact, not real repository content.

    ``.DS_Store`` is Finder's per-directory bookkeeping file. ``._<name>`` is
    an AppleDouble sidecar -- the resource-fork half of a file, written
    whenever the destination filesystem can't hold one natively (a plain zip,
    for one) -- and it shares its real counterpart's extension while being
    opaque binary, not source: left unfiltered, ``._app.py`` looks like a
    second Python module to every downstream extension check and either
    extracts as garbage or fails to parse.
    """

    return name == ".DS_Store" or name.startswith("._")


LANGUAGE_BY_EXTENSION = {
    "py": "Python",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    "js": "JavaScript",
    "jsx": "JavaScript",
    "go": "Go",
    "rs": "Rust",
    "java": "Java",
    "kt": "Kotlin",
    "swift": "Swift",
    "cs": "C#",
    "cpp": "C++",
    "c": "C",
    "html": "HTML",
    "css": "CSS",
    "scss": "SCSS",
    "json": "JSON",
    "yaml": "YAML",
    "yml": "YAML",
    "md": "Markdown",
    "sql": "SQL",
    "sh": "Shell",
}

CONFIG_FILES = {
    "package.json",
    "tsconfig.json",
    "vite.config.ts",
    "next.config.js",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    ".env.example",
    ".gitignore",
}


class RepositoryFileLimitExceeded(Exception):
    def __init__(self, max_file_count: int, file_count: int) -> None:
        super().__init__(f"repository contains more than {max_file_count} files")
        self.max_file_count = max_file_count
        self.file_count = file_count


class UnsafeRepositoryPath(Exception):
    """A repository's checked-out tree contains a symlink.

    Archive uploads already can't reach this: TAR extraction rejects
    symlink/link/device members before writing (storage/local.py), and
    Python's zipfile.extractall() never materializes a real OS symlink from
    a zip entry in the first place. A GitHub import has no such guard --
    `git clone` faithfully recreates whatever real symlinks the source
    repository committed, including ones that point outside the checkout
    (e.g. a repo containing ``ln -s /etc some_dir``). Walking that with
    plain is_dir()/is_file()/stat() (which all follow symlinks) would
    recurse into and catalog host filesystem content that was never part of
    the imported repository.
    """

    def __init__(self, relative_path: str) -> None:
        super().__init__(f"repository contains a symlink at {relative_path}")
        self.relative_path = relative_path


class RepositoryParser:
    def parse(self, root: Path, *, max_file_count: int | None = None) -> tuple[list[FileTreeNode], RepositoryMeta, int]:
        if max_file_count is not None:
            self._enforce_file_count(root, max_file_count, [0])
        tree = self._build_tree(root, root)
        flat = self._flatten(tree)
        file_nodes = [node for node in flat if node.type == "file"]
        folder_nodes = [node for node in flat if node.type == "folder"]
        total_size = sum(node.size or 0 for node in file_nodes)

        language_counter = Counter(node.language for node in file_nodes if node.language)
        language = language_counter.most_common(1)[0][0] if language_counter else "Unknown"
        config_files = [node.path.lstrip("/") for node in file_nodes if node.name in CONFIG_FILES]
        package_manager = self._detect_package_manager(root)
        framework = self._detect_framework(root)
        entry_point = self._detect_entry_point(root)
        license_name = self._detect_license(root)

        meta = RepositoryMeta(
            language=language,
            framework=framework,
            total_files=len(file_nodes),
            total_folders=len(folder_nodes),
            entry_point=entry_point,
            config_files=config_files,
            package_manager=package_manager,
            has_readme=any(node.name.lower().startswith("readme") for node in file_nodes),
            has_license=license_name is not None,
            license_name=license_name,
        )
        return tree, meta, total_size

    def _enforce_file_count(
        self, path: Path, max_file_count: int, file_count: list[int], root: Path | None = None
    ) -> None:
        """Stream the tree and abort before sorting or allocating file nodes."""

        root = root or path
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.name in IGNORED_DIRS or is_macos_artifact(entry.name):
                    continue
                if entry.is_symlink():
                    relative = "/" + str(Path(entry.path).relative_to(root)).replace("\\", "/")
                    raise UnsafeRepositoryPath(relative)
                if entry.is_dir():
                    self._enforce_file_count(Path(entry.path), max_file_count, file_count, root)
                elif entry.is_file():
                    file_count[0] += 1
                    if file_count[0] > max_file_count:
                        raise RepositoryFileLimitExceeded(max_file_count, file_count[0])

    def _build_tree(self, path: Path, root: Path) -> list[FileTreeNode]:
        nodes: list[FileTreeNode] = []
        for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            if child.name in IGNORED_DIRS or is_macos_artifact(child.name):
                continue
            relative = "/" + str(child.relative_to(root)).replace("\\", "/")
            if child.is_symlink():
                raise UnsafeRepositoryPath(relative)
            if child.is_dir():
                nodes.append(
                    FileTreeNode(
                        id=str(uuid4()),
                        name=child.name,
                        type="folder",
                        path=relative,
                        children=self._build_tree(child, root),
                    )
                )
            elif child.is_file():
                extension = child.suffix[1:].lower() if child.suffix else None
                nodes.append(
                    FileTreeNode(
                        id=str(uuid4()),
                        name=child.name,
                        type="file",
                        path=relative,
                        size=child.stat().st_size,
                        extension=extension,
                        language=LANGUAGE_BY_EXTENSION.get(extension or ""),
                    )
                )
        return nodes

    def _flatten(self, nodes: list[FileTreeNode]) -> list[FileTreeNode]:
        result: list[FileTreeNode] = []
        for node in nodes:
            result.append(node)
            if node.children:
                result.extend(self._flatten(node.children))
        return result

    def _safe_file(self, root: Path, relative: str) -> Path | None:
        """Return `root/relative` only if it's a real file that resolves inside root.

        This is best-effort metadata detection (framework/license/package
        manager guesses), unlike the file tree itself, so a symlinked
        candidate is treated as simply absent rather than failing the whole
        import: there's no recursion here, so no cycle risk, and a repo
        that happens to symlink e.g. package.json to another path within
        its own checkout is legitimate and still resolves inside root. A
        symlink pointing outside root (the actual attack: e.g. `package.json
        -> /etc/passwd` committed to a malicious repo, read here as JSON/text)
        fails the containment check and is skipped.
        """
        candidate = root / relative
        if not candidate.is_file():
            return None
        try:
            candidate.resolve().relative_to(root.resolve())
        except ValueError:
            return None
        return candidate

    def _detect_package_manager(self, root: Path) -> str | None:
        if self._safe_file(root, "pnpm-lock.yaml"):
            return "pnpm"
        if self._safe_file(root, "yarn.lock"):
            return "yarn"
        if self._safe_file(root, "package-lock.json") or self._safe_file(root, "package.json"):
            return "npm"
        if self._safe_file(root, "poetry.lock"):
            return "poetry"
        if self._safe_file(root, "requirements.txt") or self._safe_file(root, "pyproject.toml"):
            return "pip"
        return None

    def _detect_framework(self, root: Path) -> str:
        package_json = self._safe_file(root, "package.json")
        if package_json is not None:
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "next" in dependencies:
                return "Next.js"
            if "react" in dependencies:
                return "React"
            if "vue" in dependencies:
                return "Vue"
        pyproject = self._safe_file(root, "pyproject.toml")
        requirements = self._safe_file(root, "requirements.txt")
        text = ""
        if pyproject is not None:
            text += pyproject.read_text(encoding="utf-8", errors="ignore")
        if requirements is not None:
            text += requirements.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        if "fastapi" in lowered:
            return "FastAPI"
        if "django" in lowered:
            return "Django"
        if "flask" in lowered:
            return "Flask"
        return "Unknown"

    def _detect_entry_point(self, root: Path) -> str | None:
        candidates = [
            "src/main.tsx",
            "src/main.ts",
            "src/App.tsx",
            "src/app.py",
            "app/main.py",
            "main.py",
            "index.js",
            "package.json",
        ]
        for candidate in candidates:
            if self._safe_file(root, candidate):
                return f"/{candidate}"
        return None

    def _detect_license(self, root: Path) -> str | None:
        for candidate in ("LICENSE", "LICENSE.md", "COPYING"):
            safe_path = self._safe_file(root, candidate)
            if safe_path is not None:
                text = safe_path.read_text(encoding="utf-8", errors="ignore")[:500].lower()
                if "mit license" in text:
                    return "MIT"
                if "apache license" in text:
                    return "Apache-2.0"
                if "gnu general public license" in text:
                    return "GPL"
                return "Custom"
        return None
