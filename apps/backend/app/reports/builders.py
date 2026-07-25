"""Build a `ReportDocument` from an existing analysis response.

These builders never analyse a repository; they only reshape data already
produced by the existing analysis builders.
"""

from app.reports.report_document import ReportDocument, Section, Table
from app.schemas.architecture import ArchitectureResponse
from app.schemas.dependencies import DependencyGraphResponse
from app.schemas.review import EngineeringReviewResponse

_DEPENDENCY_TYPES = ("production", "development", "peer", "optional")


def build_review_document(review: EngineeringReviewResponse) -> ReportDocument:
    summary = review.summary
    severities = summary.findings_by_severity
    sections: list[Section] = [
        Section(
            heading="Executive Summary",
            paragraphs=[
                summary.message,
                "PARTHA reports only findings supported by the selected sealed snapshot. "
                "Vulnerability scanning and categories without sufficient evidence are marked Not assessed.",
            ],
            table=Table(
                headers=["Metric", "Value"],
                rows=[
                    ["Evidence-backed findings", str(summary.evidence_backed_finding_count)],
                    ["Critical", str(severities.critical)],
                    ["High", str(severities.high)],
                    ["Medium", str(severities.medium)],
                    ["Low", str(severities.low)],
                    ["Info", str(severities.info)],
                    ["Unsupported findings", str(summary.unsupported_finding_count)],
                    ["Vulnerability scanning", "Not assessed"],
                ],
            ),
        ),
        Section(
            heading="Category Assessment",
            table=Table(
                headers=["Category", "State", "Findings", "Scope"],
                rows=[
                    [
                        category.label,
                        category.state.replace("_", " "),
                        str(category.finding_count),
                        category.explanation,
                    ]
                    for category in review.categories
                ],
            ),
        ),
        Section(
            heading="Snapshot Identity",
            fields=[
                ("Revision", f"{review.revision_kind}:{review.revision_value}"),
                ("Snapshot", review.snapshot_id),
                ("Snapshot schema", review.snapshot_schema_version),
                ("Manifest digest", review.manifest_digest),
                ("Canonical graph hash", review.canonical_graph_hash),
                ("Provenance", review.provenance.source),
            ],
        ),
        Section(
            heading="Findings",
            paragraphs=[] if review.findings else ["No evidence-backed findings were identified."],
        ),
    ]

    for finding in review.findings:
        sections.append(
            Section(
                heading=f"{finding.severity.upper()}: {finding.title}",
                level=3,
                fields=[
                    ("Category", finding.category.replace("_", " ")),
                    ("Diagnostic", finding.diagnostic_code),
                    ("Rule", finding.rule_id),
                    ("Explanation", finding.explanation),
                    ("Remediation guidance", finding.remediation_guidance),
                    ("Extractor", f"{finding.extractor_name}@{finding.extractor_version}"),
                    ("Support", finding.support_status),
                ],
                bullets=[
                    f"Evidence: {finding.path}:{finding.start_line}-{finding.end_line}",
                    f"Fact: {finding.fact_id}",
                    f"Evidence ID: {finding.evidence_id}",
                    f"Snapshot: {finding.snapshot_id}",
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
                    [
                        "Vulnerability assessment",
                        dependencies.vulnerability_assessment.status.replace("_", " ").capitalize(),
                    ],
                    [
                        "Outdated-version assessment",
                        dependencies.outdated_assessment.status.replace("_", " ").capitalize(),
                    ],
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
