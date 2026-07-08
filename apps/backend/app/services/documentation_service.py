from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

from app.analysis.architecture import ArchitectureAnalyzer
from app.core.exceptions import NotFoundError, ValidationServiceError
from app.graph.dependency_graph import DependencyGraphBuilder
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.documentation import ExportRequest, ExportResponse, GenerateDocRequest, GenerateDocResponse


class DocumentationService:
    def __init__(
        self,
        repository: RepositoryRepository,
        architecture: ArchitectureAnalyzer,
        dependencies: DependencyGraphBuilder,
    ) -> None:
        self.repository = repository
        self.architecture = architecture
        self.dependencies = dependencies

    def generate(self, request: GenerateDocRequest) -> GenerateDocResponse:
        record = self.repository.get(request.repository_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": request.repository_id})
        markdown = self._markdown(record, request.sections)
        if request.format == "html":
            content = "<article>\n" + "\n".join(f"<p>{escape(line)}</p>" if line else "<br />" for line in markdown.splitlines()) + "\n</article>"
        else:
            content = markdown
        return GenerateDocResponse(content=content, format=request.format, generated_at=datetime.now(UTC))

    def export(self, request: ExportRequest) -> ExportResponse:
        if request.format not in {"json", "markdown"}:
            raise ValidationServiceError(f"{request.format.upper()} export is coming soon for {request.target}.")
        record = self.repository.get(request.repository_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": request.repository_id})
        return ExportResponse(url=f"data:application/octet-stream,{record.id}-{request.target}.{request.format}", expires_at=datetime.now(UTC) + timedelta(minutes=15))

    def _markdown(self, record: Any, sections: list[str] | None) -> str:
        selected = set(sections or ["overview", "architecture", "folder-structure", "api", "environment", "deployment", "contribution"])
        meta = record.repo_metadata or {}
        files = self._files(record.file_tree or [])
        config_files = meta.get("configFiles") or meta.get("config_files") or []
        lines = [f"# {record.name}", ""]

        if "overview" in selected:
            lines += [
                "## Overview",
                "",
                f"- Source: {record.source}",
                f"- Language: {meta.get('language', 'Unknown')}",
                f"- Framework: {meta.get('framework', 'Unknown')}",
                f"- Files: {meta.get('totalFiles') or meta.get('total_files') or record.file_count}",
                f"- Entry point: {meta.get('entryPoint') or meta.get('entry_point') or 'Not found'}",
                "",
            ]

        if "architecture" in selected:
            architecture = self.architecture.build_architecture(record)
            lines += ["## Architecture", "", f"Pattern: {architecture.architecture_type}", ""]
            for layer in architecture.detected_layers:
                lines.append(f"- {layer.name}: {len(layer.nodes)} module(s)")
            lines.append("")

        if "folder-structure" in selected:
            lines += ["## Folder Structure", "", "```text"]
            lines += files[:80] or ["No files detected."]
            lines += ["```", ""]

        if "api" in selected:
            api_files = [path for path in files if "/api/" in path or "/routes/" in path or "api" in path.lower()]
            lines += ["## API", ""]
            lines += [f"- {path}" for path in api_files[:30]] or ["No API files detected."]
            lines.append("")

        if "environment" in selected:
            env_files = [path for path in files if ".env" in path or path.endswith(("config.py", "config.ts", "config.js"))]
            lines += ["## Environment", ""]
            lines += [f"- {path}" for path in env_files[:30]] or ["No environment configuration files detected."]
            lines.append("")

        if "deployment" in selected:
            deployment_files = [path for path in files if any(token in path.lower() for token in ["docker", "deploy", "compose", "vercel", "netlify", "railway", "render"])]
            lines += ["## Deployment", ""]
            lines += [f"- {path}" for path in deployment_files[:30]] or ["No deployment files detected."]
            lines.append("")

        if "contribution" in selected:
            lines += ["## Contribution", ""]
            lines += [f"- Package manager: {meta.get('packageManager') or meta.get('package_manager') or 'Not detected'}"]
            lines += [f"- Config files: {', '.join(config_files)}" if config_files else "- Config files: Not detected"]
            lines += ["- Add setup, test, and review instructions that match this repository before onboarding contributors.", ""]

        return "\n".join(lines)

    def _files(self, nodes: list[dict[str, Any]]) -> list[str]:
        result: list[str] = []
        for node in nodes:
            if node.get("type") == "file":
                result.append(node.get("path", ""))
            result.extend(self._files(node.get("children") or []))
        return result
