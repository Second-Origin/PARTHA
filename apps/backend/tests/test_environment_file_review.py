from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord
from app.parsers.repository_parser import RepositoryParser
from app.review.review_service import EngineeringReviewBuilder


def _review(root: Path):
    tree, meta, total_size = RepositoryParser().parse(root)
    intelligence = RepositoryIntelligenceEngine().build("repo-1", "sample", root, tree, meta, total_size)
    metadata = intelligence.metadata.model_dump(mode="json", by_alias=True)
    metadata["intelligence"] = intelligence.model_dump(mode="json", by_alias=True)
    record = RepositoryRecord(
        id="repo-1",
        name="sample",
        source="upload",
        local_path=str(root),
        size=intelligence.discovery.statistics.total_size,
        file_count=intelligence.discovery.statistics.total_files,
        status="completed",
        data_source="real",
        analysis_stage="completed",
        analysis_progress=100,
        uploaded_at=datetime.now(UTC),
        analysed_at=datetime.now(UTC),
        repo_metadata=metadata,
        file_tree=[],
    )
    return intelligence, EngineeringReviewBuilder().build(record)


@pytest.mark.parametrize(
    ("filename", "content", "evidence_class", "finding_id"),
    [
        (".env.example", "API_KEY=<replace-with-real-key>\nDATABASE_URL=${DATABASE_URL}\n", "template_present", "env-template-present"),
        (".env.sample", "TOKEN=example\n", "template_present", "env-template-present"),
        (".env.template", "API_SECRET=your-secret-here\n", "template_present", "env-template-present"),
        (".env.dist", "ACCESS_TOKEN=placeholder-token\n", "template_present", "env-template-present"),
        (".env", "API_KEY=\nTOKEN=${TOKEN}\n", "runtime_env_file_present", "env-runtime-file-present"),
        (".env", "API_SECRET=super-secret\n", "secret_like_value_detected", "env-secret-like-value-detected"),
    ],
)
def test_environment_files_are_classified_by_name_and_content(
    tmp_path: Path, filename: str, content: str, evidence_class: str, finding_id: str
):
    (tmp_path / filename).write_text(content, encoding="utf-8")

    intelligence, review = _review(tmp_path)
    evidence = intelligence.discovery.environment_file_evidence
    findings = {finding.id: finding for finding in review.findings}

    assert [(item.path, item.evidence_class) for item in evidence] == [(filename, evidence_class)]
    assert finding_id in findings
    assert "Evidence class:" in findings[finding_id].problem
    if evidence_class == "secret_like_value_detected":
        assert findings[finding_id].severity == "critical"
        assert "rotate exposed secrets" in findings[finding_id].recommendation
    else:
        assert findings[finding_id].severity != "critical"
        assert "no secret rotation" in findings[finding_id].recommendation.lower()


def test_template_with_a_secret_like_value_is_not_trusted_by_filename(tmp_path: Path):
    (tmp_path / ".env.example").write_text("API_SECRET=super-secret\n", encoding="utf-8")

    intelligence, review = _review(tmp_path)
    findings = {finding.id: finding for finding in review.findings}

    assert intelligence.discovery.environment_file_evidence[0].evidence_class == "secret_like_value_detected"
    assert findings["env-secret-like-value-detected"].severity == "critical"


@pytest.mark.parametrize(
    "content",
    [
        "DATABASE_URL=postgres://user:password@localhost:5432/appdb\n",
        "DATABASE_URL=postgres://user:${DB_PASSWORD}@localhost:5432/appdb\n",
        "DATABASE_URL=postgres://user:$DB_PASSWORD@localhost:5432/appdb\n",
    ],
)
def test_placeholder_url_credentials_are_not_treated_as_secrets(tmp_path: Path, content: str):
    (tmp_path / ".env.example").write_text(content, encoding="utf-8")

    intelligence, review = _review(tmp_path)
    findings = {finding.id: finding for finding in review.findings}

    assert intelligence.discovery.environment_file_evidence[0].evidence_class == "template_present"
    assert "env-secret-like-value-detected" not in findings
    assert findings["env-template-present"].severity != "critical"


def test_real_url_credential_is_flagged_without_leaking_the_value(tmp_path: Path):
    secret_value = "9f2ab7c4d1e0"
    (tmp_path / ".env").write_text(
        f"DATABASE_URL=postgres://svc:{secret_value}@db.internal:5432/app\n", encoding="utf-8"
    )

    intelligence, review = _review(tmp_path)
    evidence = intelligence.discovery.environment_file_evidence[0]
    critical = {finding.id: finding for finding in review.findings}["env-secret-like-value-detected"]

    assert evidence.evidence_class == "secret_like_value_detected"
    assert evidence.secret_keys == ["DATABASE_URL"]
    assert critical.severity == "critical"
    assert "DATABASE_URL" in critical.problem
    # The sensitive value itself is never surfaced in the finding or the evidence.
    assert secret_value not in critical.problem
    assert all(secret_value not in key for key in evidence.secret_keys)


def test_cached_intelligence_without_environment_evidence_is_refreshed(tmp_path: Path):
    (tmp_path / ".env.example").write_text("API_KEY=<replace-with-real-key>\n", encoding="utf-8")
    tree, meta, total_size = RepositoryParser().parse(tmp_path)
    intelligence = RepositoryIntelligenceEngine().build("repo-1", "sample", tmp_path, tree, meta, total_size)
    metadata = intelligence.metadata.model_dump(mode="json", by_alias=True)
    serialized_intelligence = intelligence.model_dump(mode="json", by_alias=True)
    serialized_intelligence["discovery"].pop("environmentFileEvidence")
    metadata["intelligence"] = serialized_intelligence
    record = RepositoryRecord(
        id="repo-1",
        name="sample",
        source="upload",
        local_path=str(tmp_path),
        size=intelligence.discovery.statistics.total_size,
        file_count=intelligence.discovery.statistics.total_files,
        status="completed",
        data_source="real",
        analysis_stage="completed",
        analysis_progress=100,
        uploaded_at=datetime.now(UTC),
        analysed_at=datetime.now(UTC),
        repo_metadata=metadata,
        file_tree=tree,
    )

    review = EngineeringReviewBuilder().build(record)
    findings = {finding.id: finding for finding in review.findings}

    assert "env-template-present" in findings
    assert "env-runtime-file-present" not in findings
