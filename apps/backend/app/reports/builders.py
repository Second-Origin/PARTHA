"""Build a `ReportDocument` from an existing analysis response.

These builders never analyse a repository; they only reshape data already
produced by the Repository Intelligence Engine / existing analysis builders.
"""

from app.reports.report_document import ReportDocument, Section, Table
from app.schemas.architecture import ArchitectureResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.review import EngineeringReviewResponse

_DEPENDENCY_TYPES = ("production", "development", "peer", "optional")


def build_review_document(review: EngineeringReviewResponse) -> ReportDocument:
    summary = review.summary
    sections: list[Section] = [
        Section(
            heading="Executive Summary",
            table=Table(
                headers=["Metric", "Value"],
                rows=[
                    ["Overall Score", f"{summary.overall_score}/100"],
                    ["Overall Trend", summary.overall_trend],
                    ["Total Findings", str(summary.total_findings)],
                    ["Critical", str(summary.critical_count)],
                    ["High", str(summary.high_count)],
                    ["Medium", str(summary.medium_count)],
                    ["Low", str(summary.low_count)],
                ],
            ),
        ),
        Section(
            heading="Health Scores",
            table=Table(
                headers=["Category", "Score", "Risk", "Findings"],
                rows=[
                    [
                        score.category.replace("-", " "),
                        f"{score.score}/100",
                        score.risk_level,
                        str(score.findings_count),
                    ]
                    for score in review.scores
                ],
            ),
        ),
        Section(heading="Findings", paragraphs=[] if review.findings else ["No findings were generated."]),
    ]

    for finding in review.findings:
        sections.append(
            Section(
                heading=f"{finding.severity.upper()}: {finding.title}",
                level=3,
                fields=[
                    ("Category", finding.category.replace("-", " ")),
                    ("Effort", finding.estimated_effort),
                    ("Problem", finding.problem),
                    ("Impact", finding.impact),
                    ("Recommendation", finding.recommendation),
                ],
                bullets=[f"Affected file: {path}" for path in finding.affected_files]
                + [f"Affected module: {module}" for module in finding.affected_modules],
            )
        )

    if review.roadmap:
        sections.append(
            Section(
                heading="Improvement Roadmap",
                bullets=[
                    f"{index + 1}. {step.title} ({step.estimated_effort}) — {step.description}"
                    for index, step in enumerate(review.roadmap)
                ],
            )
        )

    return ReportDocument(
        title=f"Engineering Review: {review.repository_name}",
        subtitle=f"Generated {review.generated_at:%Y-%m-%d %H:%M UTC}",
        sections=sections,
    )


def build_architecture_document(architecture: ArchitectureResponse) -> ReportDocument:
    summary = architecture.summary
    sections: list[Section] = [
        Section(
            heading="Overview",
            table=Table(
                headers=["Property", "Value"],
                rows=[
                    ["Architecture Type", architecture.architecture_type],
                    ["Primary Language", summary.language],
                    ["Framework", summary.framework],
                    ["Entry Point", summary.entry_point],
                    ["Total Modules", str(summary.total_modules)],
                    ["Total Components", str(summary.total_nodes)],
                ],
            ),
        ),
        Section(
            heading="Layers",
            table=Table(
                headers=["Layer", "Order", "Components"],
                rows=[
                    [layer.name, str(layer.order), str(len(layer.nodes))]
                    for layer in architecture.detected_layers
                ],
            ),
        ),
        Section(
            heading="Modules",
            table=Table(
                headers=["Module", "Layer", "Files"],
                rows=[
                    [module.name, module.layer.replace("-", " "), str(module.file_count)]
                    for module in architecture.modules
                ],
            ),
        ),
    ]

    for node in architecture.nodes:
        sections.append(
            Section(
                heading=node.name,
                level=3,
                fields=[
                    ("Type", node.type.replace("-", " ")),
                    ("Layer", node.layer.replace("-", " ")),
                    ("Size Class", node.estimated_complexity),
                ],
                bullets=[f"File: {path}" for path in node.files[:10]],
            )
        )

    if architecture.request_flow:
        sections.append(
            Section(
                heading="Request Flow",
                bullets=[
                    f"{step.name} ({step.type.replace('-', ' ')}) — {step.description}"
                    for step in architecture.request_flow
                ],
            )
        )

    return ReportDocument(
        title=f"Architecture Overview: {architecture.repository_name}",
        subtitle=architecture.architecture_type,
        sections=sections,
    )


def build_dependencies_document(dependencies: DependencyGraphResponse, repository_name: str) -> ReportDocument:
    counts = {dependency_type: 0 for dependency_type in _DEPENDENCY_TYPES}
    for node in dependencies.nodes:
        counts[node.type] = counts.get(node.type, 0) + 1

    sections: list[Section] = [
        Section(
            heading="Summary",
            paragraphs=[
                "Dependency inventory is reported as detected from repository manifests. "
                "Vulnerability and outdated-version scanning are outside the current analysis scope.",
            ],
            table=Table(
                headers=["Metric", "Value"],
                rows=[
                    ["Total Dependencies", str(dependencies.total_dependencies)],
                    ["Production", str(counts["production"])],
                    ["Development", str(counts["development"])],
                    ["Peer", str(counts["peer"])],
                    ["Optional", str(counts["optional"])],
                    ["Relationships", str(len(dependencies.edges))],
                ],
            ),
        ),
        Section(
            heading="Dependencies",
            paragraphs=[] if dependencies.nodes else ["No dependencies were detected."],
            table=Table(
                headers=["Name", "Version", "Type"],
                rows=[
                    [node.name, node.version or "unknown", node.type]
                    for node in dependencies.nodes
                ],
            )
            if dependencies.nodes
            else None,
        ),
    ]

    return ReportDocument(
        title=f"Dependencies: {repository_name}",
        subtitle=f"{dependencies.total_dependencies} dependencies detected",
        sections=sections,
    )
