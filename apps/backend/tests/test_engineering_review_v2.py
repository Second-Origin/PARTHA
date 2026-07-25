"""Public Engineering Review v2 contract and provenance tests (#154)."""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from dataclasses import dataclass

from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models.repository import RepositoryRecord

from tests.analysis_helpers import run_analysis_jobs

_FINDING_SOURCES = {
    "README.md": b"# review fixture\n",
    "src/index.ts": (
        b"import { missing } from './missing';\n"
        b"export const value = missing();\n"
    ),
}
_EMPTY_SOURCES = {
    "README.md": b"# review fixture with no supported diagnostics\n",
}


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload(auth_client, files: dict[str, bytes], *, analyse: bool = True) -> dict:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("review-v2.zip", _archive(files), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    if analyse:
        assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
        assert run_analysis_jobs() == 1
    return repository


@dataclass(frozen=True)
class _FileDiagnostic:
    """A file-level diagnostic, as the extractors emit them: path, but no span."""

    path: str
    details: dict[str, object] | None = None
    object_key: str | None = None

    @property
    def subject_key(self) -> str:
        return f"file:{self.path}"


def _assert_forbidden_score_fields(value) -> None:
    forbidden = {
        "score",
        "scores",
        "overallScore",
        "categoryScore",
        "grade",
        "healthPercentage",
        "roadmap",
        "trend",
    }
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for nested in value.values():
            _assert_forbidden_score_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_forbidden_score_fields(nested)


def test_review_requires_authentication(client):
    response = client.get("/analysis/11111111-1111-1111-1111-111111111111/review")
    assert response.status_code == 401


def test_review_is_owner_scoped(auth_client, make_auth_headers):
    repository = _upload(auth_client, _FINDING_SOURCES)
    intruder = make_auth_headers("review-intruder@example.com")

    response = auth_client.get(
        f"/analysis/{repository['id']}/review",
        headers=intruder["headers"],
    )

    assert response.status_code == 404


def test_review_without_a_sealed_snapshot_returns_404(auth_client):
    repository = _upload(auth_client, _FINDING_SOURCES, analyse=False)

    response = auth_client.get(f"/analysis/{repository['id']}/review")

    assert response.status_code == 404


def test_review_contract_has_no_scores_and_is_deterministic(auth_client):
    repository = _upload(auth_client, _FINDING_SOURCES)

    first = auth_client.get(f"/analysis/{repository['id']}/review")
    second = auth_client.get(f"/analysis/{repository['id']}/review")

    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    body = first.json()
    _assert_forbidden_score_fields(body)
    assert body["schemaVersion"] == "engineering-review.v2"
    assert body["repositoryId"] == repository["id"]
    assert body["revisionValue"] == repository["revision"]["value"]
    assert body["snapshotSchemaVersion"] == "ri.v1"
    assert body["canonicalGraphHash"].startswith("sha256:")
    assert body["manifestDigest"].startswith("sha256:")
    assert body["provenance"]["source"] == "ri.v1"
    assert body["assessmentStatus"] == "partially_assessed"
    assert len({item["id"] for item in body["findings"]}) == len(body["findings"])


def test_every_public_finding_has_same_snapshot_evidence_that_opens(auth_client):
    repository = _upload(auth_client, _FINDING_SOURCES)
    review = auth_client.get(f"/analysis/{repository['id']}/review").json()

    assert review["findings"], "fixture must produce a supported resolver diagnostic"
    # Resolver diagnostics carry their own span, so every finding here must be
    # span-exact. A file-scoped finding in this fixture would mean support
    # selection had fallen back to whole-file evidence.
    assert review["summary"]["fileScopedFindingCount"] == 0
    assert review["summary"]["evidenceBackedFindingCount"] == len(review["findings"])
    for finding in review["findings"]:
        assert finding["supportStatus"] == "supported"
        assert finding["snapshotId"] == review["snapshotId"]
        assert finding["evidence"]["snapshotId"] == review["snapshotId"]
        assert finding["factId"] == finding["evidence"]["factId"]
        assert finding["evidenceId"] == finding["evidence"]["evidenceId"]
        source = auth_client.get(
            f"/analysis/{repository['id']}/evidence",
            params={
                "snapshotId": finding["snapshotId"],
                "factId": finding["factId"],
                "path": finding["path"],
                "startLine": finding["startLine"],
                "endLine": finding["endLine"],
            },
        )
        assert source.status_code == 200, source.text
        assert source.json()["status"] == "ready"


def test_review_wrong_repository_evidence_fails_closed(auth_client):
    repository_a = _upload(auth_client, _FINDING_SOURCES)
    finding = auth_client.get(f"/analysis/{repository_a['id']}/review").json()["findings"][0]
    repository_b = _upload(auth_client, {"README.md": b"# other revision\n"})

    response = auth_client.get(
        f"/analysis/{repository_b['id']}/evidence",
        params={
            "snapshotId": finding["snapshotId"],
            "factId": finding["factId"],
            "path": finding["path"],
            "startLine": finding["startLine"],
            "endLine": finding["endLine"],
        },
    )

    assert response.status_code == 404


def test_review_category_matrix_and_honest_empty_finding_state(auth_client):
    repository = _upload(auth_client, _EMPTY_SOURCES)
    body = auth_client.get(f"/analysis/{repository['id']}/review").json()

    assert body["findings"] == []
    assert body["summary"]["evidenceBackedFindingCount"] == 0
    assert "0 evidence-backed findings" in body["summary"]["message"]
    categories = {item["id"]: item for item in body["categories"]}
    assert set(categories) == {
        "architecture_boundaries",
        "relationship_resolution",
        "source_extraction",
        "dependency_declarations",
        "security_vulnerability_scanning",
        "authentication_evidence",
        "repository_structure",
        "analysis_integrity",
    }
    assert categories["analysis_integrity"]["state"] == "assessed"
    assert categories["dependency_declarations"]["state"] == "insufficient_evidence"
    assert categories["security_vulnerability_scanning"]["state"] == "not_assessed"
    assert all("score" not in item["explanation"].lower() for item in categories.values())


def _seal_snapshot_with_file_diagnostic(auth_client, *, granularity: str) -> dict:
    """Seal a snapshot whose only rule-matching diagnostic records no span.

    ``RI-SRC-MALFORMED`` and ``RI-LIMIT-SKIP`` are file-level by construction:
    the extractors emit them with a path and no span. The stored evidence for
    that path decides whether such a diagnostic can be published at all, so the
    fixture controls its granularity directly.
    """

    repository = _upload(auth_client, _EMPTY_SOURCES, analyse=False)

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        store = SnapshotStore(session)
        snapshot = store.begin(
            repository_id=record.id,
            revision=Revision(record.revision_kind, record.revision_value, record.revision_ref),
            schema_version="ri.v1",
            producer_version_set=["typescript-extractor@1.0.0", "repository-inventory@1.1.0"],
        )
        store.add_node(
            snapshot,
            node_kind="repository",
            stable_key="repo:root",
            name="repository",
            language=None,
            evidence=[
                Evidence(
                    path="README.md",
                    start_line=1,
                    end_line=1,
                    logical_line_count=2,
                    extractor="repository-inventory",
                    extractor_version="1.1.0",
                    granularity="file",
                )
            ],
        )
        store.add_node(
            snapshot,
            node_kind="file",
            stable_key="file:src/app.ts",
            name="app.ts",
            language="TypeScript",
            evidence=[
                Evidence(
                    path="src/app.ts",
                    # Deliberately not line 1: if support selection ever borrows
                    # this span for a span-less diagnostic, the finding would
                    # point at lines the diagnostic never named.
                    start_line=10,
                    end_line=12,
                    logical_line_count=40,
                    extractor="typescript-extractor",
                    extractor_version="1.0.0",
                    granularity=granularity,
                )
            ],
        )
        store.add_diagnostic(
            snapshot,
            code="RI-SRC-MALFORMED",
            category="malformed source",
            severity="error",
            message="file is not valid UTF-8 and could not be decoded",
            producer="typescript-extractor@1.0.0",
            path="src/app.ts",
            span=None,
            subject="file:src/app.ts",
        )
        store.seal(snapshot)

    response = auth_client.get(f"/analysis/{repository['id']}/review")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_span_less_diagnostic_never_borrows_a_line_addressed_evidence_span(auth_client):
    """A span-less diagnostic must not be published at someone else's span.

    The only evidence for the path is a line-addressed span the diagnostic never
    named. Publishing it would invent a location and still label the finding
    `supported`, so the diagnostic has to be omitted and counted instead.
    """

    body = _seal_snapshot_with_file_diagnostic(auth_client, granularity="span")

    assert body["findings"] == []
    assert body["summary"]["evidenceBackedFindingCount"] == 0
    assert body["summary"]["omittedUnsupportedDiagnosticCount"] >= 1
    assert body["summary"]["fileScopedFindingCount"] == 0


def test_a_file_level_diagnostic_is_published_as_file_scoped_not_as_span_exact(auth_client):
    """File-granularity evidence supports the finding, and says so."""

    body = _seal_snapshot_with_file_diagnostic(auth_client, granularity="file")

    assert len(body["findings"]) == 1
    finding = body["findings"][0]
    assert finding["diagnosticCode"] == "RI-SRC-MALFORMED"
    # The span is the file's own evidence record, and the support status states
    # that it covers the file rather than the exact defect.
    assert finding["supportStatus"] == "file_scoped"
    assert finding["path"] == "src/app.ts"
    assert (finding["startLine"], finding["endLine"]) == (10, 12)
    assert body["summary"]["fileScopedFindingCount"] == 1
    assert body["summary"]["evidenceBackedFindingCount"] == 1


def test_review_evidence_reads_stay_within_the_sql_parameter_bound(client):
    """Review reads must be batched, not sized by the repository.

    Every id set the review binds grows with the number of diagnostics. Binding
    them in one statement makes a large snapshot exceed SQLite's per-statement
    parameter cap, so a review of a big repository fails with a database error
    instead of returning. The id set here is deliberately larger than two
    batches: an unbatched read would bind all of it in one statement and exceed
    the asserted bound, so the assertion fails if the batching is removed.

    The ``client`` fixture is taken only to create the schema these reads run
    against, so the test does not depend on another test having run first.
    """

    from sqlalchemy import event

    from app.core.database import SessionLocal
    from app.intelligence.query_service import SNAPSHOT_IN_CLAUSE_BATCH_SIZE, SnapshotQueryService
    from app.review.review_service import EngineeringReviewBuilder

    identifier_count = SNAPSHOT_IN_CLAUSE_BATCH_SIZE * 2 + 1
    diagnostics = [
        _FileDiagnostic(path=f"src/module-{index:05d}.ts") for index in range(identifier_count)
    ]

    parameter_counts: list[int] = []

    def record_parameters(_conn, _cursor, _statement, parameters, _context, executemany):
        if not executemany and parameters is not None:
            parameter_counts.append(len(parameters))

    with SessionLocal() as session:
        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", record_parameters)
        try:
            builder = EngineeringReviewBuilder(SnapshotQueryService(session, "unused-owner"))
            # No snapshot has this id, so the reads return nothing. What matters
            # is the shape of the statements the builder issues to find that out.
            builder._evidence_by_fact("snap_absent", diagnostics)
        finally:
            event.remove(engine, "before_cursor_execute", record_parameters)

    assert parameter_counts, "expected to observe the evidence lookup's SQL parameters"
    # One batch of ids plus the snapshot id and any other fixed predicates.
    assert max(parameter_counts) <= SNAPSHOT_IN_CLAUSE_BATCH_SIZE + 8
    # And the work was actually spread across batches rather than skipped.
    assert len(parameter_counts) >= 3


def test_assessment_status_is_derived_from_the_category_states(auth_client):
    """The overall status must summarise the matrix, not assert a constant."""

    from app.review.review_service import _overall_assessment_status

    body = _seal_snapshot_with_file_diagnostic(auth_client, granularity="file")
    summary = body["summary"]
    states = Counter(category["state"] for category in body["categories"])

    assert body["assessmentStatus"] == _overall_assessment_status(states)
    assert states["assessed"] == summary["assessedCategories"]
    assert states["not_assessed"] == summary["notAssessedCategories"]
    # A matrix containing a not_assessed category cannot report full assessment.
    assert summary["notAssessedCategories"] >= 1
    assert body["assessmentStatus"] != "assessed"


def test_overall_assessment_status_never_overstates_coverage():
    from app.review.review_service import _overall_assessment_status

    assert _overall_assessment_status(Counter({"assessed": 8})) == "assessed"
    assert _overall_assessment_status(Counter({"assessed": 4, "not_assessed": 4})) == "partially_assessed"
    assert _overall_assessment_status(Counter({"not_assessed": 8})) == "not_assessed"
    assert (
        _overall_assessment_status(Counter({"insufficient_evidence": 2, "not_assessed": 6}))
        == "insufficient_evidence"
    )


def test_review_rejects_an_unsupported_snapshot_schema(auth_client):
    repository = _upload(auth_client, _EMPTY_SOURCES, analyse=False)

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        store = SnapshotStore(session)
        snapshot = store.begin(
            repository_id=record.id,
            revision=Revision(record.revision_kind, record.revision_value, record.revision_ref),
            schema_version="ri.v99",
            producer_version_set=["repository-inventory@1.1.0"],
        )
        store.add_node(
            snapshot,
            node_kind="repository",
            stable_key="repo:root",
            name="repository",
            language=None,
            evidence=[
                Evidence(
                    path="README.md",
                    start_line=1,
                    end_line=1,
                    logical_line_count=2,
                    extractor="repository-inventory",
                    extractor_version="1.1.0",
                )
            ],
        )
        store.seal(snapshot)

    response = auth_client.get(f"/analysis/{repository['id']}/review")
    assert response.status_code == 422
