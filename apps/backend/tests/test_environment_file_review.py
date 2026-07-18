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
        "PASSWORD_MIN_LENGTH=12\n",
        "TOKEN_EXPIRY_SECONDS=3600\n",
        "CLIENT_SECRET_REQUIRED=true\n",
        "API_KEY_ENABLED=false\n",
        "PRIVATE_KEY_PATH=/run/keys/service.pem\n",
    ],
)
def test_security_related_configuration_is_not_credible_secret_evidence(tmp_path: Path, content: str):
    (tmp_path / ".env").write_text(content, encoding="utf-8")

    intelligence, review = _review(tmp_path)
    findings = {finding.id: finding for finding in review.findings}

    assert intelligence.discovery.environment_file_evidence[0].evidence_class == "runtime_env_file_present"
    assert "env-secret-like-value-detected" not in findings
    assert findings["env-runtime-file-present"].severity == "medium"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("SECRET_KEY", "synthetic-secret-123"),
        ("AUTH_SECRET_KEY", "synthetic-secret-123"),
        ("DJANGO_SECRET_KEY", "synthetic-secret-123"),
        ("SESSION_SECRET_KEY", "synthetic-secret-123"),
    ],
)
def test_secret_key_names_with_credible_values_remain_secret_evidence(tmp_path: Path, key: str, value: str):
    (tmp_path / ".env").write_text(f"{key}={value}\n", encoding="utf-8")

    intelligence, review = _review(tmp_path)
    evidence = intelligence.discovery.environment_file_evidence[0]
    findings = {finding.id: finding for finding in review.findings}

    assert evidence.evidence_class == "secret_like_value_detected"
    assert evidence.secret_keys == [key]
    assert findings["env-secret-like-value-detected"].severity == "critical"


@pytest.mark.parametrize(
    "content",
    [
        "TOKEN=${TOKEN} # access token\n",
        'API_KEY="${API_KEY}" # required\n',
    ],
)
def test_placeholder_before_inline_comment_is_not_treated_as_a_secret(tmp_path: Path, content: str):
    (tmp_path / ".env.example").write_text(content, encoding="utf-8")

    intelligence, review = _review(tmp_path)
    findings = {finding.id: finding for finding in review.findings}

    assert intelligence.discovery.environment_file_evidence[0].evidence_class == "template_present"
    assert "env-secret-like-value-detected" not in findings
    assert findings["env-template-present"].severity == "low"


def test_hash_inside_quoted_secret_is_not_parsed_as_an_inline_comment(tmp_path: Path):
    (tmp_path / ".env").write_text('API_SECRET="real-secret#fragment" # deployment credential\n', encoding="utf-8")

    intelligence, review = _review(tmp_path)

    assert intelligence.discovery.environment_file_evidence[0].evidence_class == "secret_like_value_detected"
    assert "env-secret-like-value-detected" in {finding.id for finding in review.findings}


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


def test_cached_intelligence_without_environment_evidence_uses_bounded_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
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

    engine = RepositoryIntelligenceEngine()
    monkeypatch.setattr(engine, "build", lambda *args, **kwargs: pytest.fail("legacy cache must not be rebuilt"))

    loaded = engine.from_record(record)
    review = EngineeringReviewBuilder(engine).build(record)
    findings = {finding.id: finding for finding in review.findings}

    assert loaded.discovery.environment_file_evidence[0].evidence_class == "runtime_env_file_present"
    assert "env-template-present" not in findings
    assert findings["env-runtime-file-present"].severity == "medium"
