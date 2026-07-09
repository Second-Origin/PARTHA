from datetime import UTC, datetime

from app.analysis.architecture import ArchitectureAnalyzer
from app.core.exceptions import NotFoundError
from app.graph.dependency_graph import DependencyGraphBuilder
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.repositories.repository_repository import RepositoryRepository
from app.reports.renderers import render_html, render_markdown
from app.reports.report_document import ReportDocument, Section
from app.schemas.documentation import GenerateDocRequest, GenerateDocResponse

DEFAULT_SECTIONS = ["overview", "architecture", "folder-structure", "api", "environment", "deployment", "contribution"]


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
        document = self._document(self._get_record(request.repository_id), request.sections)
        content = render_html(document) if request.format == "html" else render_markdown(document)
        return GenerateDocResponse(content=content, format=request.format, generated_at=datetime.now(UTC))

    def build_document(self, repository_id: str) -> ReportDocument:
        return self._document(self._get_record(repository_id), None)

    def _get_record(self, repository_id: str):
        record = self.repository.get(repository_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": repository_id})
        return record

    def _document(self, record, sections: list[str] | None) -> ReportDocument:
        selected = set(sections or DEFAULT_SECTIONS)
        repository_intelligence = self.intelligence.from_record(record)
        discovery = repository_intelligence.discovery
        files = [file.path for file in repository_intelligence.files]
        report_sections: list[Section] = []

        if "overview" in selected:
            report_sections.append(
                Section(
                    heading="Overview",
                    fields=[
                        ("Source", record.source),
                        ("Primary language", discovery.primary_language),
                        ("Frameworks", ", ".join(discovery.frameworks) if discovery.frameworks else "Not detected"),
                        ("Files", str(discovery.statistics.total_files)),
                        ("Source files", str(discovery.statistics.source_files)),
                        ("Entry point", ", ".join(discovery.entry_points) if discovery.entry_points else "Not found"),
                    ],
                )
            )

        if "architecture" in selected:
            architecture = self.architecture.build_architecture(record)
            report_sections.append(
                Section(
                    heading="Architecture",
                    fields=[("Pattern", architecture.architecture_type)],
                    bullets=[f"{layer.name}: {len(layer.nodes)} module(s)" for layer in architecture.detected_layers],
                )
            )

        if "folder-structure" in selected:
            report_sections.append(Section(heading="Folder Structure", bullets=files[:80] or ["No files detected."]))

        if "api" in selected:
            api_files = [file.path for file in repository_intelligence.files if file.role in {"route", "controller"} or file.api_routes]
            api_routes = [route for file in repository_intelligence.files for route in file.api_routes]
            report_sections.append(
                Section(
                    heading="API",
                    bullets=[f"File: {path}" for path in api_files[:30]]
                    + [f"Route: {route}" for route in api_routes[:30]]
                    or ["No API files detected."],
                )
            )

        if "environment" in selected:
            report_sections.append(
                Section(
                    heading="Environment",
                    bullets=discovery.environment_files[:30] or ["No environment configuration files detected."],
                )
            )

        if "deployment" in selected:
            deployment_files = sorted(set(discovery.docker_files + discovery.ci_files))
            report_sections.append(
                Section(heading="Deployment", bullets=deployment_files[:30] or ["No deployment files detected."])
            )

        if "contribution" in selected:
            report_sections.append(
                Section(
                    heading="Contribution",
                    fields=[
                        ("Package managers", ", ".join(discovery.package_managers) if discovery.package_managers else "Not detected"),
                        ("Config files", ", ".join(discovery.configuration_files[:20]) if discovery.configuration_files else "Not detected"),
                    ],
                    paragraphs=["Add setup, test, and review instructions that match this repository before onboarding contributors."],
                )
            )

        return ReportDocument(
            title=record.name,
            subtitle=f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC}",
            sections=report_sections,
        )
