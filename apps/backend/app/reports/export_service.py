"""Turn existing analysis reports into downloadable JSON / Markdown / HTML / PDF.

The service only consumes data from the existing analysis and documentation
builders (which read the Repository Intelligence Engine); it never re-analyses a
repository. Content is returned inline so the API stays JSON and is testable:
text formats as UTF-8, PDF as base64.
"""

import base64
import json

from app.core.exceptions import ValidationServiceError
from app.reports.builders import build_review_document
from app.reports.renderers import render_html, render_markdown, render_pdf
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
        # Gather the report's structured data via the existing builders.
        # These raise NotFoundError when the repository does not exist.
        response = self._load_report(request)

        if request.format == "json":
            payload = json.dumps(response.model_dump(mode="json", by_alias=True), indent=2)
            return self._text(slug, "json", "application/json", payload)

        # Markdown/HTML/PDF are rendered from a ReportDocument, which currently
        # exists only for the engineering-review report.
        document = self._build_document(request.target, response)
        if document is None:
            raise ValidationServiceError(
                f"{request.format.upper()} export is not available yet for the "
                f"{request.target} report. Export it as JSON instead.",
                {"target": request.target, "format": request.format},
            )

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

    def _build_document(self, target: str, response):
        if target == "review":
            return build_review_document(response)
        return None

    def _text(self, slug: str, extension: str, media_type: str, content: str) -> ExportResponse:
        return ExportResponse(
            filename=f"{slug}.{extension}",
            media_type=media_type,
            encoding="utf-8",
            content=content,
        )
