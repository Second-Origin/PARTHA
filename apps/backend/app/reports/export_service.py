"""Turn existing analysis reports into downloadable JSON / Markdown / HTML / PDF.

The service only consumes data from the existing analysis and documentation
builders (which read the Repository Intelligence Engine); it never re-analyses a
repository. Content is returned inline so the API stays JSON and is testable:
text formats as UTF-8, PDF as base64.
"""

import base64
import json

from app.reports.builders import (
    build_architecture_document,
    build_dependencies_document,
    build_review_document,
)
from app.reports.renderers import render_html, render_markdown, render_pdf
from app.reports.report_document import ReportDocument
from app.schemas.documentation import GenerateDocRequest
from app.schemas.reports import ExportRequest, ExportResponse
from app.services.analysis_service import AnalysisService
from app.services.documentation_service import DocumentationService

_SLUGS = {
    "review": "engineering-review",
    "documentation": "documentation",
    "architecture": "architecture",
    "dependencies": "dependencies",
}


class ExportService:
    def __init__(self, analysis: AnalysisService, documentation: DocumentationService) -> None:
        self.analysis = analysis
        self.documentation = documentation

    def export(self, request: ExportRequest) -> ExportResponse:
        slug = _SLUGS[request.target]

        # JSON serialises the raw report response; the other formats render a
        # ReportDocument. Both paths raise NotFoundError for a missing repository.
        if request.format == "json":
            response = self._load_report(request)
            payload = json.dumps(response.model_dump(mode="json", by_alias=True), indent=2)
            return self._text(slug, "json", "application/json", payload)

        document = self._build_document(request)

        if request.format == "markdown":
            return self._text(slug, "md", "text/markdown", render_markdown(document))
        if request.format == "html":
            return self._text(slug, "html", "text/html", render_html(document))
        # request.format == "pdf"
        pdf_bytes = render_pdf(document)
        return ExportResponse(
            filename=f"{slug}.pdf",
            media_type="application/pdf",
            encoding="base64",
            content=base64.b64encode(pdf_bytes).decode("ascii"),
        )

    def _load_report(self, request: ExportRequest):
        if request.target == "review":
            return self.analysis.engineering_review(request.repository_id)
        if request.target == "architecture":
            return self.analysis.architecture_model(request.repository_id)
        if request.target == "dependencies":
            return self.analysis.dependency_graph(request.repository_id)
        return self.documentation.generate(GenerateDocRequest(repository_id=request.repository_id))

    def _build_document(self, request: ExportRequest) -> ReportDocument:
        if request.target == "review":
            return build_review_document(self.analysis.engineering_review(request.repository_id))
        if request.target == "architecture":
            return build_architecture_document(self.analysis.architecture_model(request.repository_id))
        if request.target == "dependencies":
            graph = self.analysis.dependency_graph(request.repository_id)
            record = self.analysis.repository.get(request.repository_id)
            return build_dependencies_document(graph, record.name if record else request.repository_id)
        return self.documentation.build_document(request.repository_id)

    def _text(self, slug: str, extension: str, media_type: str, content: str) -> ExportResponse:
        return ExportResponse(
            filename=f"{slug}.{extension}",
            media_type=media_type,
            encoding="utf-8",
            content=content,
        )
