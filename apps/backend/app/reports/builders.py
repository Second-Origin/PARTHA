"""Build a `ReportDocument` from an existing analysis response.

These builders never analyse a repository; they only reshape data already
produced by the Repository Intelligence Engine / existing analysis builders.
"""

from app.reports.report_document import ReportDocument, Section, Table
from app.schemas.review import EngineeringReviewResponse


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
