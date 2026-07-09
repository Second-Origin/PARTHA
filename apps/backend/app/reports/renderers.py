"""Render a `ReportDocument` to Markdown, HTML, or PDF.

HTML is produced from the intermediate representation directly; PDF reuses that
same HTML through xhtml2pdf, so the two formats never drift apart.
"""

from html import escape
from io import BytesIO

from xhtml2pdf import pisa

from app.core.exceptions import ServiceError
from app.reports.report_document import ReportDocument, Section

_HTML_STYLES = """
body { font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; font-size: 11px; }
h1 { font-size: 20px; margin-bottom: 2px; }
h2 { font-size: 15px; margin-top: 18px; border-bottom: 1px solid #ccc; padding-bottom: 3px; }
h3 { font-size: 12px; margin-top: 12px; }
p { margin: 4px 0; }
.subtitle { color: #666; font-size: 10px; }
table { border-collapse: collapse; width: 100%; margin: 6px 0; }
th, td { border: 1px solid #ccc; padding: 4px 6px; text-align: left; font-size: 10px; }
th { background-color: #f2f2f2; }
ul { margin: 4px 0; }
li { margin: 2px 0; }
"""


def render_markdown(document: ReportDocument) -> str:
    lines: list[str] = [f"# {document.title}", ""]
    if document.subtitle:
        lines += [f"_{document.subtitle}_", ""]
    for section in document.sections:
        lines.append(f"{'#' * section.level} {section.heading}")
        lines.append("")
        for label, value in section.fields:
            lines += [f"**{label}:** {value}", ""]
        for paragraph in section.paragraphs:
            lines += [paragraph, ""]
        if section.table:
            lines.append("| " + " | ".join(section.table.headers) + " |")
            lines.append("| " + " | ".join("---" for _ in section.table.headers) + " |")
            for row in section.table.rows:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")
        for bullet in section.bullets:
            lines.append(f"- {bullet}")
        if section.bullets:
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(document: ReportDocument) -> str:
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html><head><meta charset="utf-8">',
        f"<title>{escape(document.title)}</title>",
        f"<style>{_HTML_STYLES}</style>",
        "</head><body>",
        f"<h1>{escape(document.title)}</h1>",
    ]
    if document.subtitle:
        parts.append(f'<p class="subtitle">{escape(document.subtitle)}</p>')
    for section in document.sections:
        parts.append(_render_section_html(section))
    parts.append("</body></html>")
    return "\n".join(parts)


def render_pdf(document: ReportDocument) -> bytes:
    buffer = BytesIO()
    result = pisa.CreatePDF(src=render_html(document), dest=buffer)
    if result.err:
        raise ServiceError("Failed to render the report as PDF.")
    return buffer.getvalue()


def _render_section_html(section: Section) -> str:
    level = min(max(section.level, 2), 6)
    parts = [f"<h{level}>{escape(section.heading)}</h{level}>"]
    for label, value in section.fields:
        parts.append(f"<p><strong>{escape(label)}:</strong> {escape(value)}</p>")
    for paragraph in section.paragraphs:
        parts.append(f"<p>{escape(paragraph)}</p>")
    if section.table:
        head = "".join(f"<th>{escape(header)}</th>" for header in section.table.headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
            for row in section.table.rows
        )
        parts.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
    if section.bullets:
        items = "".join(f"<li>{escape(bullet)}</li>" for bullet in section.bullets)
        parts.append(f"<ul>{items}</ul>")
    return "\n".join(parts)
