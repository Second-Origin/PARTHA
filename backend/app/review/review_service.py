from datetime import UTC, datetime

from app.models.repository import RepositoryRecord
from app.schemas.review import EngineeringReviewResponse, ImprovementStep, ReviewFinding, ReviewScore, ReviewSummary


class EngineeringReviewBuilder:
    def build(self, record: RepositoryRecord) -> EngineeringReviewResponse:
        findings = self._findings(record)
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

    def _findings(self, record: RepositoryRecord) -> list[ReviewFinding]:
        meta = record.repo_metadata or {}
        file_tree = record.file_tree or []
        files = self._files(file_tree)
        findings: list[ReviewFinding] = []

        if not meta.get("hasReadme"):
            findings.append(self._finding("doc-no-readme", "Missing README", "documentation", "high", "Add a README with setup, architecture, and contribution guidance."))
        if not meta.get("hasLicense"):
            findings.append(self._finding("doc-no-license", "Missing License", "documentation", "medium", "Add an explicit license or proprietary notice."))
        if not any(".test." in path or ".spec." in path or "__tests__" in path for path in files):
            findings.append(self._finding("test-missing", "No Tests Detected", "testing", "high", "Add automated unit and integration tests for critical paths."))
        if any(path.endswith(".env") for path in files):
            findings.append(self._finding("env-file-present", "Environment File Present", "security", "critical", "Remove committed secret-bearing environment files."))
        if len(files) > 300:
            findings.append(self._finding("large-codebase", "Large File Surface", "architecture", "medium", "Define module boundaries and public interfaces."))

        if not findings:
            findings.append(self._finding("baseline-review", "Baseline Review Complete", "maintainability", "low", "Keep quality gates active as backend analysis deepens."))
        return findings

    def _finding(self, finding_id: str, title: str, category: str, severity: str, recommendation: str) -> ReviewFinding:
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
            affected_files=[],
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

    def _files(self, nodes: list[dict]) -> list[str]:
        result: list[str] = []
        for node in nodes:
            if node.get("type") == "file":
                result.append(node.get("path", ""))
            result.extend(self._files(node.get("children") or []))
        return result
