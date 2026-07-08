from datetime import UTC, datetime

from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.schemas.review import EngineeringReviewResponse, ImprovementStep, ReviewFinding, ReviewScore, ReviewSummary


class EngineeringReviewBuilder:
    def __init__(self, intelligence: RepositoryIntelligenceEngine | None = None) -> None:
        self.intelligence = intelligence or RepositoryIntelligenceEngine()

    def build(self, record: RepositoryRecord) -> EngineeringReviewResponse:
        repository_intelligence = self.intelligence.from_record(record)
        findings = self._findings(repository_intelligence)
        scores = self._scores(findings)
        summary = self._summary(findings, scores)
        roadmap = self._roadmap(findings)
        return EngineeringReviewResponse(
            repository_id=record.id,
            repository_name=record.name,
            generated_at=datetime.now(UTC),
            summary=summary,
            scores=scores,
            findings=findings,
            roadmap=roadmap,
        )

    def _findings(self, intelligence) -> list[ReviewFinding]:
        discovery = intelligence.discovery
        files = intelligence.files
        findings: list[ReviewFinding] = []

        if not intelligence.metadata.has_readme:
            findings.append(self._finding("doc-no-readme", "Missing README", "documentation", "high", "Add a README with setup, architecture, and contribution guidance.", []))
        if not intelligence.metadata.has_license:
            findings.append(self._finding("doc-no-license", "Missing License", "documentation", "medium", "Add an explicit license or proprietary notice.", []))
        if discovery.statistics.test_files == 0:
            findings.append(self._finding("test-missing", "No Tests Detected", "testing", "high", "Add automated unit and integration tests for critical paths.", []))
        if discovery.environment_files:
            findings.append(self._finding("env-file-present", "Environment File Present", "security", "critical", "Remove committed secret-bearing environment files.", discovery.environment_files))
        if discovery.statistics.source_files > 300:
            findings.append(self._finding("large-codebase", "Large Source Surface", "architecture", "medium", "Define module boundaries and public interfaces.", [file.path for file in files[:25]]))
        if not discovery.ci_files:
            findings.append(self._finding("ci-missing", "No CI Workflow Detected", "code-quality", "medium", "Add CI to run build, lint, and test checks on pull requests.", []))
        if not findings:
            findings.append(self._finding("baseline-review", "Baseline Review Complete", "maintainability", "low", "Keep quality gates active as repository intelligence deepens.", []))
        return findings

    def _finding(self, finding_id: str, title: str, category: str, severity: str, recommendation: str, files: list[str]) -> ReviewFinding:
        return ReviewFinding(
            id=finding_id,
            title=title,
            category=category,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            status="open",
            problem=title,
            impact="This can reduce maintainability, correctness, or operational confidence.",
            recommendation=recommendation,
            priority={"critical": 1, "high": 2, "medium": 3, "low": 4}[severity],
            estimated_effort="small" if severity in {"low", "medium"} else "medium",
            affected_files=files,
            affected_modules=["repository"],
            tags=[category],
        )

    def _scores(self, findings: list[ReviewFinding]) -> list[ReviewScore]:
        categories = ["architecture", "security", "performance", "maintainability", "scalability", "code-quality", "documentation", "testing", "dependency-health", "configuration"]
        severity_cost = {"critical": 35, "high": 20, "medium": 10, "low": 5}
        scores: list[ReviewScore] = []
        for index, category in enumerate(categories, start=1):
            category_findings = [finding for finding in findings if finding.category == category]
            score = max(0, 100 - sum(severity_cost[finding.severity] for finding in category_findings))
            risk = "critical" if score < 40 else "high" if score < 65 else "medium" if score < 85 else "low"
            scores.append(
                ReviewScore(
                    category=category,  # type: ignore[arg-type]
                    score=score,
                    trend="stable",
                    risk_level=risk,  # type: ignore[arg-type]
                    priority=index,
                    findings_count=len(category_findings),
                )
            )
        return scores

    def _summary(self, findings: list[ReviewFinding], scores: list[ReviewScore]) -> ReviewSummary:
        return ReviewSummary(
            overall_score=round(sum(score.score for score in scores) / max(len(scores), 1)),
            overall_trend="stable",
            critical_count=len([finding for finding in findings if finding.severity == "critical"]),
            high_count=len([finding for finding in findings if finding.severity == "high"]),
            medium_count=len([finding for finding in findings if finding.severity == "medium"]),
            low_count=len([finding for finding in findings if finding.severity == "low"]),
            total_findings=len(findings),
        )

    def _roadmap(self, findings: list[ReviewFinding]) -> list[ImprovementStep]:
        return [
            ImprovementStep(
                id="quality-gates",
                title="Establish Quality Gates",
                description="Add automated linting, type checking, tests, and dependency scanning.",
                priority="high",
                estimated_effort="1 sprint",
                category="code-quality",
                related_findings=[finding.id for finding in findings],
            )
        ]
