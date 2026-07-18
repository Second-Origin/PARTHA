from datetime import UTC, datetime

from app.intelligence.engine import RepositoryIntelligenceEngine
from app.intelligence.models import EnvironmentFileEvidence
from app.models.repository import RepositoryRecord
from app.schemas.review import EngineeringReviewResponse, ImprovementStep, ReviewFinding, ReviewScore, ReviewSummary

LARGE_FILE_BYTES = 40_000
LARGE_SOURCE_SURFACE = 300
SEVERITY_PRIORITY = {"critical": 1, "high": 2, "medium": 3, "low": 4}
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
EFFORT_BY_SEVERITY = {"critical": "1 sprint", "high": "1 sprint", "medium": "a few days", "low": "a few hours"}


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
        statistics = discovery.statistics
        files = intelligence.files
        findings: list[ReviewFinding] = []

        if not intelligence.metadata.has_readme:
            findings.append(
                self._finding(
                    "doc-no-readme",
                    "Missing README",
                    "documentation",
                    "high",
                    problem=f"No README file was detected among {statistics.documentation_files} documentation file(s).",
                    impact="Contributors and reviewers lack setup, architecture, and usage guidance, which slows onboarding and increases misuse.",
                    recommendation="Add a README covering setup, architecture, and contribution guidance.",
                    affected_files=[],
                    affected_modules=["documentation"],
                )
            )
        if not intelligence.metadata.has_license:
            findings.append(
                self._finding(
                    "doc-no-license",
                    "Missing License",
                    "documentation",
                    "medium",
                    problem="No license file or explicit license declaration was detected.",
                    impact="Without a declared license the code's usage and distribution rights are ambiguous, blocking adoption and reuse.",
                    recommendation="Add an explicit open-source license or a proprietary notice.",
                    affected_files=[],
                    affected_modules=["documentation"],
                )
            )
        if statistics.test_files == 0:
            findings.append(
                self._finding(
                    "test-missing",
                    "No Tests Detected",
                    "testing",
                    "high",
                    problem=f"No test files were detected among {statistics.source_files} source file(s).",
                    impact="Changes cannot be validated automatically, so regressions can reach production undetected.",
                    recommendation="Add automated unit and integration tests for critical paths.",
                    affected_files=[],
                    affected_modules=["tests"],
                )
            )
        environment_evidence: list[EnvironmentFileEvidence] = discovery.environment_file_evidence
        if not environment_evidence and discovery.environment_files:
            environment_evidence = [
                EnvironmentFileEvidence(path=path, evidence_class="runtime_env_file_present")
                for path in discovery.environment_files
            ]
        template_files = [item.path for item in environment_evidence if item.evidence_class == "template_present"]
        runtime_files = [item.path for item in environment_evidence if item.evidence_class == "runtime_env_file_present"]
        secret_evidence = [item for item in environment_evidence if item.evidence_class == "secret_like_value_detected"]
        secret_files = [item.path for item in secret_evidence]
        secret_keys = sorted({key for item in secret_evidence for key in item.secret_keys})
        if secret_files:
            findings.append(
                self._finding(
                    "env-secret-like-value-detected",
                    "Secret-Like Environment Value Detected",
                    "security",
                    "critical",
                    problem=(
                        "Evidence class: secret-like value detected. Committed environment file(s) contain "
                        f"non-placeholder values for sensitive key(s): {', '.join(secret_keys[:10])}."
                    ),
                    impact="Secrets committed to version control can be leaked and abused, and remain recoverable from history.",
                    recommendation="Remove committed secret-bearing environment files, rotate exposed secrets, and ignore them going forward.",
                    affected_files=secret_files,
                    affected_modules=["configuration"],
                )
            )
        if runtime_files:
            findings.append(
                self._finding(
                    "env-runtime-file-present",
                    "Runtime Environment File Present",
                    "security",
                    "medium",
                    problem=(
                        "Evidence class: runtime env file present. These committed files had no detected secret-like value, "
                        "so their filenames alone are not evidence of an exposed secret."
                    ),
                    impact="A runtime environment file can later accumulate credentials or be copied into deployments without review.",
                    recommendation="Keep runtime environment files out of version control and review their values. No secret rotation is indicated unless a secret-like value is detected.",
                    affected_files=runtime_files,
                    affected_modules=["configuration"],
                )
            )
        if template_files:
            findings.append(
                self._finding(
                    "env-template-present",
                    "Environment Template Present",
                    "configuration",
                    "low",
                    problem=(
                        "Evidence class: template present. These files document environment configuration and contain no detected "
                        "secret-like value."
                    ),
                    impact="Templates are safe to commit when they remain placeholder-only, but they should not be used as a location for live credentials.",
                    recommendation="Keep templates placeholder-only and document required variables; no secret rotation is indicated by this finding.",
                    affected_files=template_files,
                    affected_modules=["configuration"],
                )
            )
        if statistics.source_files > LARGE_SOURCE_SURFACE:
            findings.append(
                self._finding(
                    "large-codebase",
                    "Large Source Surface",
                    "architecture",
                    "medium",
                    problem=f"The repository has {statistics.source_files} source files, a large surface to keep coherent.",
                    impact="A large undivided surface makes ownership, change impact, and public interfaces hard to reason about.",
                    recommendation="Define module boundaries and public interfaces to contain change impact.",
                    affected_files=[file.path for file in files[:25]],
                )
            )
        large_files = sorted(
            (file for file in files if file.role != "documentation" and file.size > LARGE_FILE_BYTES),
            key=lambda file: file.size,
            reverse=True,
        )
        if large_files:
            findings.append(
                self._finding(
                    "large-files",
                    "Oversized Source Files",
                    "maintainability",
                    "medium",
                    problem=f"{len(large_files)} file(s) exceed {LARGE_FILE_BYTES // 1000} KB, a sign of low cohesion or god-files.",
                    impact="Oversized files are harder to review, test, and refactor safely, concentrating risk in a few places.",
                    recommendation="Split large files along clear responsibilities and extract cohesive units.",
                    affected_files=[file.path for file in large_files[:10]],
                )
            )
        if not discovery.ci_files:
            findings.append(
                self._finding(
                    "ci-missing",
                    "No CI Workflow Detected",
                    "code-quality",
                    "medium",
                    problem="No continuous-integration workflow configuration was detected.",
                    impact="Build, lint, and test checks are not enforced on changes, letting regressions merge unnoticed.",
                    recommendation="Add CI to run build, lint, and test checks on pull requests.",
                    affected_files=[],
                    affected_modules=["configuration"],
                )
            )
        if not findings:
            findings.append(
                self._finding(
                    "baseline-review",
                    "Baseline Review Complete",
                    "maintainability",
                    "low",
                    problem="No blocking issues were detected by the current repository intelligence checks.",
                    impact="The repository meets the baseline checks; continued discipline keeps quality high.",
                    recommendation="Keep quality gates active as repository intelligence deepens.",
                    affected_files=[],
                )
            )
        return findings

    def _finding(
        self,
        finding_id: str,
        title: str,
        category: str,
        severity: str,
        problem: str,
        impact: str,
        recommendation: str,
        affected_files: list[str],
        affected_modules: list[str] | None = None,
    ) -> ReviewFinding:
        return ReviewFinding(
            id=finding_id,
            title=title,
            category=category,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            status="open",
            problem=problem,
            impact=impact,
            recommendation=recommendation,
            priority=SEVERITY_PRIORITY[severity],
            estimated_effort="small" if severity in {"low", "medium"} else "medium",
            affected_files=affected_files,
            affected_modules=affected_modules or ["repository"],
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
        actionable = [finding for finding in findings if finding.id != "baseline-review"]
        if not actionable:
            return [
                ImprovementStep(
                    id="maintain-quality-gates",
                    title="Maintain Quality Gates",
                    description="Keep linting, type checking, tests, and dependency scanning active as the repository grows.",
                    priority="low",
                    estimated_effort="ongoing",
                    category="code-quality",
                    related_findings=[finding.id for finding in findings],
                )
            ]

        grouped: dict[str, list[ReviewFinding]] = {}
        for finding in actionable:
            grouped.setdefault(finding.category, []).append(finding)

        steps: list[ImprovementStep] = []
        for category, group in grouped.items():
            top_severity = min((finding.severity for finding in group), key=lambda severity: SEVERITY_RANK[severity])
            steps.append(
                ImprovementStep(
                    id=f"roadmap-{category}",
                    title=f"Address {category.replace('-', ' ')} findings",
                    description="; ".join(dict.fromkeys(finding.recommendation for finding in group)),
                    priority=top_severity,  # type: ignore[arg-type]
                    estimated_effort=EFFORT_BY_SEVERITY[top_severity],
                    category=category,  # type: ignore[arg-type]
                    related_findings=[finding.id for finding in group],
                )
            )
        steps.sort(key=lambda step: SEVERITY_RANK[step.priority])
        return steps
