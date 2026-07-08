import json
import tomllib
from pathlib import Path

import networkx as nx

from app.models.repository import RepositoryRecord
from app.schemas.dependencies import DependencyEdge, DependencyGraphResponse, DependencyNode


class DependencyGraphBuilder:
    def build(self, record: RepositoryRecord) -> DependencyGraphResponse:
        root = Path(record.local_path)
        graph = nx.DiGraph()
        dependencies = self._read_dependencies(root)
        for name, version, dep_type in dependencies:
            graph.add_node(name, version=version, type=dep_type)

        nodes = [
            DependencyNode(
                id=name,
                name=name,
                version=data.get("version", "unknown"),
                type=data.get("type", "production"),
                has_vulnerabilities=False,
                is_outdated=False,
                size=None,
            )
            for name, data in graph.nodes(data=True)
        ]
        edges = [DependencyEdge(source=source, target=target, type="depends-on") for source, target in graph.edges()]
        return DependencyGraphResponse(
            repository_id=record.id,
            nodes=nodes,
            edges=edges,
            total_dependencies=len(nodes),
            vulnerabilities=0,
            outdated=0,
        )

    def _read_dependencies(self, root: Path) -> list[tuple[str, str, str]]:
        deps: list[tuple[str, str, str]] = []
        package_json = root / "package.json"
        if package_json.exists():
            data = json.loads(package_json.read_text(encoding="utf-8"))
            for section, dep_type in (("dependencies", "production"), ("devDependencies", "development"), ("peerDependencies", "peer"), ("optionalDependencies", "optional")):
                for name, version in data.get(section, {}).items():
                    deps.append((name, str(version), dep_type))

        requirements = root / "requirements.txt"
        if requirements.exists():
            for line in requirements.read_text(encoding="utf-8", errors="ignore").splitlines():
                clean = line.strip()
                if not clean or clean.startswith("#"):
                    continue
                name = clean.split("==")[0].split(">=")[0].split("<=")[0].strip()
                deps.append((name, clean.replace(name, "", 1) or "unknown", "production"))

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project_deps = data.get("project", {}).get("dependencies", [])
            for item in project_deps:
                name = str(item).split("==")[0].split(">=")[0].split("<=")[0].strip()
                deps.append((name, str(item).replace(name, "", 1) or "unknown", "production"))
        return deps
