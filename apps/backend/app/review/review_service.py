from datetime import UTC, datetime
from pathlib import PurePosixPath

from app.intelligence.engine import SOURCE_EXTENSIONS, RepositoryIntelligenceEngine
from app.intelligence.models import SourceFileIntelligence
from app.models.repository import RepositoryRecord
from app.schemas.review import (
    EngineeringReviewResponse,
    ImprovementStep,
    ReviewFileEvidence,
    ReviewFinding,
    ReviewScore,
    ReviewSummary,
)

LARGE_FILE_BYTES = 40_000
LARGE_SOURCE_SURFACE = 300
SEVERITY_PRIORITY = {"critical": 1, "high": 2, "medium": 3, "low": 4}
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
EFFORT_BY_SEVERITY = {"critical": "1 sprint", "high": "1 sprint", "medium": "a few days", "low": "a few hours"}

# The oversized-source review is intentionally limited to refactorable authored
# code. Lockfiles, configuration, generated/minified code, vendored code, and
# build outputs are not design evidence, even when they are large.
LOCKFILE_NAMES = frozenset(
    {
        "bun.lockb",
        "cargo.lock",
        "composer.lock",
        "gemfile.lock",
        "go.sum",
        "mix.lock",
        "npm-shrinkwrap.json",
        "package-lock.json",
        "pdm.lock",
        "pipfile.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "yarn.lock",
    }
)
ARTIFACT_DIRECTORY_NAMES = frozenset(
    {
        ".next",
        ".nuxt",
        "__generated__",
        "bin",
        "build",
        "coverage",
        "dist",
        "gen",
        "generated",
        "node_modules",
        "obj",
        "out",
        "target",
        "third-party",
        "third_party",
        "vendor",
    }
)
GENERATED_SOURCE_SUFFIXES = (
    ".designer.cs",
    ".g.cs",
    ".g.ts",
    ".gen.js",
    ".gen.ts",
    ".gen.tsx",
    ".generated.js",
    ".generated.py",
    ".generated.ts",
    ".generated.tsx",
    ".min.cjs",
    ".min.js",
    ".min.mjs",
    ".pb.go",
    "_pb2.py",
    "_pb2_grpc.py",
)
CONFIGURATION_SOURCE_SUFFIXES = (
    ".conf.js",
    ".conf.ts",
    ".config.js",
    ".config.ts",
    ".config.tsx",
)


def _is_refactorable_source_file(file: SourceFileIntelligence) -> bool:
    """Return whether a file is authored source eligible for the size review.

    The rules are path- and metadata-based so the review does not infer a
    maintainability problem from generated or dependency-managed artifacts.
    """

    path = PurePosixPath(file.path.casefold())
    name = path.name
    return (
        file.size > LARGE_FILE_BYTES
        and file.extension in SOURCE_EXTENSIONS
        and file.role not in {"configuration", "documentation"}
        and name not in LOCKFILE_NAMES
        and not any(part in ARTIFACT_DIRECTORY_NAMES for part in path.parts)
        and not name.endswith(GENERATED_SOURCE_SUFFIXES)
        and not name.endswith(CONFIGURATION_SOURCE_SUFFIXES)
    )


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
        if discovery.environment_files:
            findings.append(
                self._finding(
                    "env-file-present",
                    "Environment File Present",
                    "security",
                    "critical",
                    problem=f"Committed environment file(s) that may contain secrets: {', '.join(discovery.environment_files[:5])}.",
                    impact="Secrets committed to version control can be leaked and abused, and remain recoverable from history.",
                    recommendation="Remove committed secret-bearing environment files, rotate exposed secrets, and ignore them going forward.",
                    affected_files=discovery.environment_files,
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
            (file for file in files if _is_refactorable_source_file(file)),
            key=lambda file: file.size,
            reverse=True,
        )
        if large_files:
            large_file_evidence = [
                ReviewFileEvidence(path=file.path, size_bytes=file.size) for file in large_files[:10]
            ]
            findings.append(
                self._finding(
                    "large-files",
                    "Oversized Source Files",
                    "maintainability",
                    "medium",
                    problem=(
                        f"{len(large_files)} authored source file(s) exceed {LARGE_FILE_BYTES // 1000} KB. "
                        "Size is a review signal; it does not establish a design problem by itself."
                    ),
                    impact=(
                        "Large authored source files can require more context to review, test, and change safely, "
                        "so they merit a focused review before any refactoring decision."
                    ),
                    recommendation=(
                        "Review the listed files with their measured sizes as context; refactor only where "
                        "responsibilities or complexity warrant it."
                    ),
                    affected_files=[evidence.path for evidence in large_file_evidence],
                    affected_file_details=large_file_evidence,
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
        affected_file_details: list[ReviewFileEvidence] | None = None,
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
            affected_file_details=affected_file_details or [],
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
