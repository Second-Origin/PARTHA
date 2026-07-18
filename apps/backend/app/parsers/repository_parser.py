import json
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
}

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


class RepositoryParser:
    def parse(self, root: Path) -> tuple[list[FileTreeNode], RepositoryMeta, int]:
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

    def _build_tree(self, path: Path, root: Path) -> list[FileTreeNode]:
        nodes: list[FileTreeNode] = []
        for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            if child.name in IGNORED_DIRS:
                continue
            relative = "/" + str(child.relative_to(root)).replace("\\", "/")
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

    def _detect_package_manager(self, root: Path) -> str | None:
        if (root / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (root / "yarn.lock").exists():
            return "yarn"
        if (root / "package-lock.json").exists() or (root / "package.json").exists():
            return "npm"
        if (root / "poetry.lock").exists():
            return "poetry"
        if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
            return "pip"
        return None

    def _detect_framework(self, root: Path) -> str:
        package_json = root / "package.json"
        if package_json.exists():
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
        pyproject = root / "pyproject.toml"
        requirements = root / "requirements.txt"
        text = ""
        if pyproject.exists():
            text += pyproject.read_text(encoding="utf-8", errors="ignore")
        if requirements.exists():
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
            if (root / candidate).exists():
                return f"/{candidate}"
        return None

    def _detect_license(self, root: Path) -> str | None:
        for candidate in ("LICENSE", "LICENSE.md", "COPYING"):
            if (root / candidate).exists():
                text = (root / candidate).read_text(encoding="utf-8", errors="ignore")[:500].lower()
                if "mit license" in text:
                    return "MIT"
                if "apache license" in text:
                    return "Apache-2.0"
                if "gnu general public license" in text:
                    return "GPL"
                return "Custom"
        return None
