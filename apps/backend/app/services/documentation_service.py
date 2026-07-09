from datetime import UTC, datetime
from html import escape

from app.analysis.architecture import ArchitectureAnalyzer
from app.core.exceptions import NotFoundError
from app.graph.dependency_graph import DependencyGraphBuilder
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.documentation import GenerateDocRequest, GenerateDocResponse


class DocumentationService:
    def __init__(
        self,
        repository: RepositoryRepository,
        architecture: ArchitectureAnalyzer,
        dependencies: DependencyGraphBuilder,
        intelligence: RepositoryIntelligenceEngine | None = None,
    ) -> None:
        self.repository = repository
        self.architecture = architecture
        self.dependencies = dependencies
        self.intelligence = intelligence or RepositoryIntelligenceEngine()

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

    def _markdown(self, record, sections: list[str] | None) -> str:
        selected = set(sections or ["overview", "architecture", "folder-structure", "api", "environment", "deployment", "contribution"])
        repository_intelligence = self.intelligence.from_record(record)
        discovery = repository_intelligence.discovery
        files = [file.path for file in repository_intelligence.files]
        lines = [f"# {record.name}", ""]

        if "overview" in selected:
            lines += [
                "## Overview",
                "",
                f"- Source: {record.source}",
                f"- Primary language: {discovery.primary_language}",
                f"- Frameworks: {', '.join(discovery.frameworks) if discovery.frameworks else 'Not detected'}",
                f"- Files: {discovery.statistics.total_files}",
                f"- Source files: {discovery.statistics.source_files}",
                f"- Entry point: {', '.join(discovery.entry_points) if discovery.entry_points else 'Not found'}",
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
            api_files = [file.path for file in repository_intelligence.files if file.role in {"route", "controller"} or file.api_routes]
            api_routes = [route for file in repository_intelligence.files for route in file.api_routes]
            lines += ["## API", ""]
            lines += [f"- {path}" for path in api_files[:30]] or ["No API files detected."]
            if api_routes:
                lines += ["", "Detected routes:", *[f"- {route}" for route in api_routes[:30]]]
            lines.append("")

        if "environment" in selected:
            lines += ["## Environment", ""]
            lines += [f"- {path}" for path in discovery.environment_files[:30]] or ["No environment configuration files detected."]
            lines.append("")

        if "deployment" in selected:
            deployment_files = sorted(set(discovery.docker_files + discovery.ci_files))
            lines += ["## Deployment", ""]
            lines += [f"- {path}" for path in deployment_files[:30]] or ["No deployment files detected."]
            lines.append("")

        if "contribution" in selected:
            lines += ["## Contribution", ""]
            lines += [f"- Package managers: {', '.join(discovery.package_managers) if discovery.package_managers else 'Not detected'}"]
            lines += [f"- Config files: {', '.join(discovery.configuration_files[:20])}" if discovery.configuration_files else "- Config files: Not detected"]
            lines += ["- Add setup, test, and review instructions that match this repository before onboarding contributors.", ""]

        return "\n".join(lines)
