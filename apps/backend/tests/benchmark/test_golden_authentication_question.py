"""The #95 golden question, run against the real production chain end to end.

Issue #94's harness scores raw node/observation/diagnostic extraction; it has
no notion of "ask a question, get a scored answer." This test is that missing
piece for the one golden question #95 requires: it runs the exact production
chain (extraction -> resolution -> role classification -> sealing) over the
committed ``real-py-auth-service`` fixture, queries the sealed snapshot
exclusively through :class:`SnapshotQueryService`, and asserts the
:class:`AuthenticationExplanationService` answer against hand-authored
expected facts — the same discipline the rest of the corpus uses, extended
past raw extraction to the actual consumer-facing answer.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analysis.authentication import AuthenticationExplanationService
from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.pipeline import ExtractionPipeline, ProducedExtraction
from app.extraction.python import PythonExtractor
from app.intelligence.classification import RoleClassifier
from app.intelligence.query_service import SnapshotQueryService
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base

from benchmark import paths
from benchmark.loader import load_corpus, load_support_matrix

GOLDEN_QUESTION = (
    "Explain how authentication works in this repository, citing exact "
    "routes, middleware, services, models, dependencies, symbols, and line spans."
)
FIXTURE_ID = "real-py-auth-service"

EXPECTED_ROUTES = {"/me"}
EXPECTED_MIDDLEWARE = {"get_current_user"}
EXPECTED_SERVICES = {"UserService"}
EXPECTED_MODELS = {"UserModel"}


def _load_fixture():
    support_matrix = load_support_matrix(paths.SUPPORT_MATRIX_PATH)
    fixtures = load_corpus(paths.FIXTURES_DIR, support_matrix)
    fixture = next(item for item in fixtures if item.fixture_id == FIXTURE_ID)
    return fixture


def _evidence(record, produced: ProducedExtraction) -> Evidence:
    return Evidence(
        path=record.path,
        start_line=record.start_line,
        end_line=record.end_line,
        extractor=produced.producer_name,
        extractor_version=produced.producer_version,
        logical_line_count=record.logical_line_count,
        granularity=record.granularity,
    )


def _seal_fixture(db_path) -> tuple[str, str]:
    """Run the real production chain and return (owner_id, repository_id)."""

    fixture = _load_fixture()
    runs = ExtractionPipeline(
        (PythonExtractor(),), max_source_bytes=fixture.max_source_bytes
    ).run(fixture.source_files())

    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    owner = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@example.com", password_hash=None)
    session.add(owner)
    session.commit()

    revision_value = fixture.revision_value()
    repository = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name="real-py-auth-service",
        source="upload",
        revision_kind="upload",
        revision_value=revision_value,
        revision_ref=None,
        local_path="/stored/revision",
        status="completed",
        file_tree=[],
    )
    session.add(repository)
    session.commit()

    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", revision_value),
        producer_version_set=[
            "python-ast@1.0.0",
            "repository-inventory@1.0.0",
            f"{RelationshipResolver.name}@{RelationshipResolver.version}",
            f"{RoleClassifier.name}@{RoleClassifier.version}",
        ],
        config={"max_source_bytes": fixture.max_source_bytes},
    )
    for produced in runs:
        for node in produced.result.nodes:
            store.add_node(
                snapshot,
                node_kind=node.node_kind,
                stable_key=node.stable_key,
                name=node.name,
                language=node.language,
                properties=node.properties,
                set_array_keys=(
                    frozenset({"decorators"})
                    if node.properties and "decorators" in node.properties
                    else frozenset()
                ),
                evidence=[_evidence(item, produced) for item in node.evidence],
            )
        for observation in produced.result.observations:
            store.add_observation(
                snapshot,
                observed_kind=observation.observed_kind,
                subject_kind=observation.subject_kind,
                subject_key=observation.subject_key,
                referent_text=observation.referent_text,
                ordinal=observation.ordinal,
                evidence=_evidence(observation.evidence, produced),
            )
        for diagnostic in produced.result.diagnostics:
            store.add_diagnostic(
                snapshot,
                code=diagnostic.code,
                category=diagnostic.category,
                severity=diagnostic.severity,
                message=diagnostic.message,
                producer=produced.producer,
                path=diagnostic.path,
                span=diagnostic.span,
                subject=diagnostic.subject,
                details=diagnostic.details,
            )

    RelationshipResolver(store).resolve(snapshot)
    RoleClassifier(store).classify(snapshot)
    sealed = store.seal(snapshot)

    return session, owner.id, repository.id, sealed.snapshot_id


def test_golden_authentication_question(tmp_path):
    """The fixed golden question (#95), answered by the real production chain."""

    session, owner_id, repository_id, snapshot_id = _seal_fixture(tmp_path / "golden.db")
    try:
        record = session.get(RepositoryRecord, repository_id)
        query_service = SnapshotQueryService(session, owner_id)
        service = AuthenticationExplanationService(query_service)

        response = service.explain(record)

        assert response.status == "ready", GOLDEN_QUESTION
        assert response.snapshot_id == snapshot_id

        by_kind: dict[str, set[str]] = {}
        for claim in response.claims:
            by_kind.setdefault(claim.kind, set()).add(claim.name)

        assert by_kind.get("route") == EXPECTED_ROUTES
        assert by_kind.get("middleware") == EXPECTED_MIDDLEWARE
        assert by_kind.get("service") == EXPECTED_SERVICES
        assert by_kind.get("model") == EXPECTED_MODELS

        # No unsupported claim: every emitted kind is one #95 declares meaningful,
        # and nothing beyond the expected four sets was produced.
        assert set(by_kind) <= {"route", "middleware", "service", "model", "dependency"}

        # Every citation resolves to the exact fixture revision, path, and span.
        source = (
            _load_fixture().source_files()["src/service.py"].decode("utf-8").splitlines()
        )
        for claim in response.claims:
            assert claim.evidence, f"claim {claim.name!r} has no evidence"
            for citation in claim.evidence:
                assert citation.snapshot_id == snapshot_id
                assert citation.path == "src/service.py"
                assert 1 <= citation.start_line <= citation.end_line <= len(source)

        # The route -> handler -> middleware chain is itself evidence-backed.
        relationship_pairs = {(item.subject, item.predicate, item.object) for item in response.relationships}
        assert ("/me", "routes_to", "read_me") in relationship_pairs
        assert ("read_me", "injects", "get_current_user") in relationship_pairs
        for relationship in response.relationships:
            assert relationship.evidence

        # oauth2_scheme is referenced but never defined in the fixture: it must
        # surface as a visible "could not resolve" diagnostic, never be silently
        # dropped or fabricated as a resolved middleware claim.
        assert any(diagnostic.code == "RI-RES-UNRESOLVED" for diagnostic in response.diagnostics)
        assert "oauth2_scheme" not in {claim.name for claim in response.claims}
    finally:
        session.close()
