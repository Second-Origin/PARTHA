"""Presentation-agnostic report model.

Report builders produce a `ReportDocument` from existing analysis responses; the
renderers turn that single structure into Markdown, HTML, or PDF. Keeping this
intermediate representation separate from the renderers is what lets a new
export format be added without touching any builder.
"""

from dataclasses import dataclass, field


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]


@dataclass
class Section:
    heading: str
    level: int = 2
    fields: list[tuple[str, str]] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    table: Table | None = None


@dataclass
class ReportDocument:
    title: str
    subtitle: str | None = None
    sections: list[Section] = field(default_factory=list)
