from datetime import UTC, datetime

from app.core.exceptions import NotFoundError
from app.intelligence.query_service import ProductSnapshotProjection, SnapshotQueryService
from app.repositories.repository_repository import RepositoryRepository
from app.reports.renderers import render_html, render_markdown
from app.reports.report_document import ReportDocument, Section
from app.schemas.documentation import GenerateDocRequest, GenerateDocResponse

DEFAULT_SECTIONS = ["overview", "architecture", "folder-structure", "api", "environment", "deployment", "contribution"]


class DocumentationService:
    def __init__(
        self,
        repository: RepositoryRepository,
        snapshots: SnapshotQueryService,
        owner_id: str,
    ) -> None:
        self.repository = repository
        self.snapshots = snapshots
        self.owner_id = owner_id

    def generate(self, request: GenerateDocRequest) -> GenerateDocResponse:
        record = self._get_record(request.repository_id)
        projection = self.snapshots.product_projection(record.id)
        document = self._document(record, projection, request.sections)
        content = render_html(document) if request.format == "html" else render_markdown(document)
        return GenerateDocResponse(
            content=content,
            format=request.format,
            generated_at=datetime.now(UTC),
            source="ri.v1",
            snapshot_id=projection.snapshot_id,
            snapshot_schema_version=projection.schema_version,
            revision_kind=projection.revision_kind,
            revision_value=projection.revision_value,
            revision_ref=projection.revision_ref,
        )

    def build_document(self, repository_id: str) -> ReportDocument:
        record = self._get_record(repository_id)
        return self._document(record, self.snapshots.product_projection(record.id), None)

    def _get_record(self, repository_id: str):
        # Owner-scoped: another user's repository id resolves to None, yielding
        # the same 404 as a missing one rather than confirming it exists.
        record = self.repository.get_for_owner(repository_id, self.owner_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": repository_id})
        return record

    def _document(
        self,
        record,
        projection: ProductSnapshotProjection,
        sections: list[str] | None,
    ) -> ReportDocument:
        selected = set(sections or DEFAULT_SECTIONS)
        files = [file.path for file in projection.files]
        report_sections: list[Section] = []

        if "overview" in selected:
            source_files = sum(file.language is not None for file in projection.files)
            report_sections.append(
                Section(
                    heading="Overview",
                    fields=[
                        ("Source", record.source),
                        ("Primary language", projection.primary_language),
                        ("Frameworks", ", ".join(projection.frameworks) if projection.frameworks else "Not detected"),
                        ("Observed files", str(len(projection.files))),
                        ("Observed supported-language files", str(source_files)),
                        ("Entry point", ", ".join(projection.entry_points) if projection.entry_points else "Not detected"),
                    ],
                )
            )

        if "architecture" in selected:
            report_sections.append(
                Section(
                    heading="Architecture",
                    fields=[("Basis", "Modules are deterministic groupings of observed paths; roles are heuristic classifications.")],
                    bullets=[
                        f"{module.name}: {module.role} (heuristic), {len(module.paths)} observed file(s)"
                        for module in projection.modules
                    ]
                    or ["No modules detected."],
                )
            )

        if "folder-structure" in selected:
            report_sections.append(Section(heading="Folder Structure", bullets=files[:80] or ["No files detected."]))

        if "api" in selected:
            api_files = sorted(
                {
                    file.path
                    for file in projection.files
                    if file.role in {"route", "controller"}
                }
                | {path for route in projection.routes for path in route.evidence_paths}
            )
            report_sections.append(
                Section(
                    heading="API",
                    bullets=[f"File: {path}" for path in api_files[:30]]
                    + [f"Observed route: {route.path}" for route in projection.routes[:30]]
                    or ["No routes detected in the supported snapshot facts."],
                )
            )

        if "environment" in selected:
            environment_files = sorted(
                path
                for path in files
                if path.rsplit("/", 1)[-1].lower().startswith(".env")
                or path.rsplit("/", 1)[-1].lower() in {"settings.py", "config.py", "config.ts", "config.js"}
            )
            report_sections.append(
                Section(
                    heading="Environment",
                    bullets=environment_files[:30] or ["No environment/configuration paths detected."],
                )
            )

        if "deployment" in selected:
            deployment_files = sorted(
                path
                for path in files
                if "dockerfile" in path.lower()
                or path.lower().startswith(".github/workflows/")
                or path.lower().endswith((".yml", ".yaml"))
                and any(token in path.lower() for token in ("deploy", "compose", "ci"))
            )
            report_sections.append(
                Section(
                    heading="Deployment",
                    bullets=deployment_files[:30] or ["No deployment-related paths detected."],
                )
            )

        if "contribution" in selected:
            ecosystems = sorted({item.ecosystem for item in projection.dependencies if item.ecosystem})
            manifests = sorted(
                {
                    declaration.manifest_path
                    for dependency in projection.dependencies
                    for declaration in dependency.declarations
                    if declaration.manifest_path
                }
            )
            report_sections.append(
                Section(
                    heading="Contribution",
                    fields=[
                        ("Dependency ecosystems", ", ".join(ecosystems) if ecosystems else "Not detected"),
                        ("Observed manifests", ", ".join(manifests[:20]) if manifests else "Not detected"),
                    ],
                    paragraphs=[
                        "Setup, test, and review commands are not inferred from path inventory; verify repository instructions directly."
                    ],
                    bullets=[
                        (
                            f"{dependency.name}: "
                            f"{declaration.version or 'no version/specifier declared'}"
                            f" ({declaration.manifest_path or 'manifest path unavailable'})"
                        )
                        for dependency in projection.dependencies
                        for declaration in dependency.declarations
                    ][:50]
                    or ["No supported dependency declarations detected."],
                )
            )

        return ReportDocument(
            title=record.name,
            subtitle=(
                f"Sealed {projection.schema_version} snapshot {projection.snapshot_id}; "
                f"revision {projection.revision_kind}:{projection.revision_value}"
            ),
            sections=report_sections,
        )
