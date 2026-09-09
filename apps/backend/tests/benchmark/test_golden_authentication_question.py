"""The #95 golden question, run against a dedicated, honest benchmark set.

Issue #94's 23-fixture corpus scores raw node/observation/diagnostic
extraction accuracy; it has no notion of "ask a question, get a scored
answer," and its fixtures and thresholds are not touched here. This is a
*separate*, smaller, hand-authored set of 5 fixtures built specifically to
answer one fixed question against the real production chain end to end
(extraction -> resolution -> role classification -> sealing -> query). Do not
conflate the two counts: this module answers the golden *authentication*
question against these 5 fixtures; #94 proves raw extraction accuracy
against its own 23.

Only Python/FastAPI-style ``Depends()`` dependency injection is a supported
authentication-detection path today (see app/intelligence/classification.py
and app/extraction/python.py's ``_DEPENDENCY_MARKERS``). TypeScript appears in
one fixture only as an inert sibling file that manufactures a genuine
cross-language import ambiguity; it is not a second supported authentication
language, and no TypeScript-native dependency-injection idiom is claimed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.analysis.authentication import AuthenticationExplanationService
from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.pipeline import ExtractionPipeline, ProducedExtraction
from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence import canonical
from app.intelligence.classification import RoleClassifier
from app.intelligence.query_service import SnapshotQueryService
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base
from app.schemas.authentication import AuthenticationExplanationResponse

GOLDEN_QUESTION = (
    "Explain how authentication works in this repository, citing exact "
    "routes, middleware, services, models, dependencies, symbols, and line spans."
)


@dataclass(frozen=True)
class AuthQuestionFixture:
    """One hand-authored authentication-question scenario and its exact expected answer."""

    fixture_id: str
    sources: dict[str, bytes]
    expected_routes: frozenset[str]
    expected_middleware: frozenset[str]
    expected_services: frozenset[str]
    expected_models: frozenset[str]
    expected_relationship_pairs: frozenset[tuple[str, str, str]]
    forbidden_names: frozenset[str] = field(default_factory=frozenset)
    expected_diagnostic_codes: frozenset[str] = field(default_factory=frozenset)


_CONNECTED = AuthQuestionFixture(
    fixture_id="connected_auth_path",
    sources={
        "src/dependencies.py": (
            b"from src.services import UserService\n\n\n"
            b"def get_current_user(token: str) -> dict:\n"
            b"    return UserService(token)\n"
        ),
        "src/services.py": (
            b"from src.models import UserModel\n\n\ndef UserService(token: str) -> dict:\n    return UserModel(token)\n"
        ),
        "src/models.py": (b"def UserModel(token: str) -> dict:\n    return {'token': token}\n"),
        "src/routes.py": (
            b"from fastapi import FastAPI, Depends\n"
            b"from src.dependencies import get_current_user\n\n"
            b"app = FastAPI()\n\n\n"
            b'@app.get("/me")\n'
            b"def read_me(user=Depends(get_current_user)):\n"
            b"    return user\n"
        ),
    },
    expected_routes=frozenset({"/me"}),
    expected_middleware=frozenset({"get_current_user"}),
    expected_services=frozenset({"UserService"}),
    expected_models=frozenset({"UserModel"}),
    expected_relationship_pairs=frozenset(
        {
            ("/me", "routes_to", "read_me"),
            ("read_me", "injects", "get_current_user"),
            ("get_current_user", "calls", "UserService"),
            ("UserService", "calls", "UserModel"),
        }
    ),
)

_UNRELATED_NOISE = AuthQuestionFixture(
    fixture_id="unrelated_noise_excluded",
    sources={
        "src/dependencies.py": (
            b"from src.services import UserService\n\n\n"
            b"def get_current_user(token: str) -> dict:\n"
            b"    return UserService(token)\n\n\n"
            b"def get_database() -> str:\n"
            b"    return 'db-session'\n"
        ),
        "src/services.py": (
            b"from src.models import UserModel\n\n\n"
            b"def UserService(token: str) -> dict:\n"
            b"    return UserModel(token)\n\n\n"
            b"def PaymentService(amount: int) -> int:\n"
            b"    return amount\n"
        ),
        "src/models.py": (
            b"def UserModel(token: str) -> dict:\n"
            b"    return {'token': token}\n\n\n"
            b"def AuditModel(event: str) -> dict:\n"
            b"    return {'event': event}\n"
        ),
        "src/routes.py": (
            b"from fastapi import FastAPI, Depends\n"
            b"from src.dependencies import get_current_user, get_database\n\n"
            b"app = FastAPI()\n\n\n"
            b'@app.get("/me")\n'
            b"def read_me(user=Depends(get_current_user)):\n"
            b"    return user\n\n\n"
            b'@app.get("/health")\n'
            b"def health_check(db=Depends(get_database)):\n"
            b"    return {'status': 'ok'}\n"
        ),
    },
    expected_routes=frozenset({"/me"}),
    expected_middleware=frozenset({"get_current_user"}),
    expected_services=frozenset({"UserService"}),
    expected_models=frozenset({"UserModel"}),
    expected_relationship_pairs=frozenset(
        {
            ("/me", "routes_to", "read_me"),
            ("read_me", "injects", "get_current_user"),
            ("get_current_user", "calls", "UserService"),
            ("UserService", "calls", "UserModel"),
        }
    ),
    forbidden_names=frozenset({"/health", "health_check", "get_database", "PaymentService", "AuditModel"}),
)

_GENERIC_DEPENDENCY_ONLY = AuthQuestionFixture(
    fixture_id="generic_dependency_not_auth",
    sources={
        "src/dependencies.py": b"def get_database() -> str:\n    return 'db-session'\n",
        "src/routes.py": (
            b"from fastapi import FastAPI, Depends\n"
            b"from src.dependencies import get_database\n\n"
            b"app = FastAPI()\n\n\n"
            b'@app.get("/health")\n'
            b"def health_check(db=Depends(get_database)):\n"
            b"    return {'status': 'ok'}\n"
        ),
    },
    expected_routes=frozenset(),
    expected_middleware=frozenset(),
    expected_services=frozenset(),
    expected_models=frozenset(),
    expected_relationship_pairs=frozenset(),
    forbidden_names=frozenset({"/health", "health_check", "get_database"}),
)

_UNRESOLVED_AND_AMBIGUOUS = AuthQuestionFixture(
    fixture_id="unresolved_and_ambiguous_gaps",
    sources={
        "src/routes.py": (
            b"from fastapi import FastAPI, Depends\n"
            b"from .shared import get_current_user\n"
            b"from src.dependencies import missing_guard\n\n"
            b"app = FastAPI()\n\n\n"
            b'@app.get("/me")\n'
            b"def read_me(user=Depends(get_current_user)):\n"
            b"    return user\n\n\n"
            b'@app.get("/profile")\n'
            b"def read_profile(user=Depends(missing_guard)):\n"
            b"    return user\n"
        ),
        # Both files define `get_current_user`; the relative import binding
        # resolves to both candidate files, so the reference stays a
        # deterministic RI-RES-AMBIGUOUS diagnostic rather than guessing.
        "src/shared.py": b"def get_current_user(token: str) -> str:\n    return token\n",
        "src/shared.ts": (b"export function get_current_user(token: string): string {\n  return token;\n}\n"),
    },
    expected_routes=frozenset(),
    expected_middleware=frozenset(),
    expected_services=frozenset(),
    expected_models=frozenset(),
    expected_relationship_pairs=frozenset(),
    forbidden_names=frozenset({"/me", "/profile", "read_me", "read_profile", "get_current_user", "missing_guard"}),
    expected_diagnostic_codes=frozenset({"RI-RES-UNRESOLVED", "RI-RES-AMBIGUOUS"}),
)

_NO_AUTH_CONSTRUCTS = AuthQuestionFixture(
    fixture_id="no_auth_constructs",
    sources={"src/plain.py": b"def add(a, b):\n    return a + b\n"},
    expected_routes=frozenset(),
    expected_middleware=frozenset(),
    expected_services=frozenset(),
    expected_models=frozenset(),
    expected_relationship_pairs=frozenset(),
)

FIXTURES = [
    _CONNECTED,
    _UNRELATED_NOISE,
    _GENERIC_DEPENDENCY_ONLY,
    _UNRESOLVED_AND_AMBIGUOUS,
    _NO_AUTH_CONSTRUCTS,
]
FIXTURE_IDS = [item.fixture_id for item in FIXTURES]


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


def _seal_sources(db_path, sources: dict[str, bytes]) -> tuple[Session, str, str, str]:
    """Run the real production chain and return (session, owner_id, repository_id, snapshot_id)."""

    runs = ExtractionPipeline((PythonExtractor(), TypeScriptExtractor())).run(sources)

    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    owner = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@example.com", password_hash=None)
    session.add(owner)
    session.commit()

    digest_map = {path: canonical.sha256_hex(data) for path, data in sources.items()}
    revision_value = canonical.sha256_prefixed(canonical.canonical_json_bytes(digest_map))
    repository = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name="auth-question-fixture",
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
        producer_version_set=sorted(
            {run.producer for run in runs}
            | {
                f"{RelationshipResolver.name}@{RelationshipResolver.version}",
                f"{RoleClassifier.name}@{RoleClassifier.version}",
            }
        ),
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
                    frozenset({"decorators"}) if node.properties and "decorators" in node.properties else frozenset()
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


def _explain(session: Session, owner_id: str, repository_id: str) -> AuthenticationExplanationResponse:
    record = session.get(RepositoryRecord, repository_id)
    assert record is not None
    query_service = SnapshotQueryService(session, owner_id)
    service = AuthenticationExplanationService(query_service)
    return service.explain(record)


@pytest.mark.parametrize("fixture", FIXTURES, ids=FIXTURE_IDS)
def test_golden_authentication_question(fixture: AuthQuestionFixture, tmp_path) -> None:
    """The fixed golden question (#95), answered by the real production chain
    against each of the 5 dedicated authentication-question fixtures."""

    session, owner_id, repository_id, snapshot_id = _seal_sources(
        tmp_path / f"{fixture.fixture_id}.db", fixture.sources
    )
    try:
        response = _explain(session, owner_id, repository_id)

        assert response.status == "ready", GOLDEN_QUESTION
        assert response.snapshot_id == snapshot_id

        by_kind: dict[str, set[str]] = {}
        for claim in response.claims:
            by_kind.setdefault(claim.kind, set()).add(claim.name)

        assert by_kind.get("route", set()) == fixture.expected_routes
        assert by_kind.get("middleware", set()) == fixture.expected_middleware
        assert by_kind.get("service", set()) == fixture.expected_services
        assert by_kind.get("model", set()) == fixture.expected_models

        relationship_pairs = {(item.subject, item.predicate, item.object) for item in response.relationships}
        assert relationship_pairs == fixture.expected_relationship_pairs

        # No unsupported claim: nothing forbidden for this scenario leaked
        # into a claim or a relationship endpoint.
        all_names: set[str] = set()
        for names in by_kind.values():
            all_names |= names
        for relationship in response.relationships:
            all_names.add(relationship.subject)
            all_names.add(relationship.object)
        leaked = all_names & fixture.forbidden_names
        assert not leaked, f"{fixture.fixture_id}: forbidden names leaked into the answer: {leaked}"

        diagnostic_codes = {diagnostic.code for diagnostic in response.diagnostics}
        assert fixture.expected_diagnostic_codes <= diagnostic_codes

        # Every citation resolves to the exact fixture revision, path, and span.
        source_line_counts = {
            path: len(content.decode("utf-8").splitlines()) for path, content in fixture.sources.items()
        }
        for claim in response.claims:
            assert claim.evidence, f"claim {claim.name!r} has no evidence"
            for citation in claim.evidence:
                assert citation.snapshot_id == snapshot_id
                assert citation.path in source_line_counts
                assert 1 <= citation.start_line <= citation.end_line <= source_line_counts[citation.path]
        for relationship in response.relationships:
            assert relationship.evidence, f"{relationship.subject} -> {relationship.object} has no evidence"
            for citation in relationship.evidence:
                assert citation.snapshot_id == snapshot_id
                assert citation.path in source_line_counts
                assert 1 <= citation.start_line <= citation.end_line <= source_line_counts[citation.path]
    finally:
        session.close()


@pytest.mark.parametrize("fixture", FIXTURES, ids=FIXTURE_IDS)
def test_golden_authentication_question_is_deterministic(fixture: AuthQuestionFixture, tmp_path) -> None:
    """Sealing the same sources twice, independently, must answer identically."""

    first_session, first_owner, first_repo, _ = _seal_sources(tmp_path / "first.db", fixture.sources)
    second_session, second_owner, second_repo, _ = _seal_sources(tmp_path / "second.db", fixture.sources)
    try:
        first = _explain(first_session, first_owner, first_repo)
        second = _explain(second_session, second_owner, second_repo)

        def _shape(response: AuthenticationExplanationResponse):
            return (
                response.status,
                frozenset((claim.kind, claim.name, claim.confidence) for claim in response.claims),
                frozenset((item.subject, item.predicate, item.object) for item in response.relationships),
                frozenset(
                    (diagnostic.code, diagnostic.path, diagnostic.start_line, diagnostic.end_line)
                    for diagnostic in response.diagnostics
                ),
            )

        assert _shape(first) == _shape(second)
    finally:
        first_session.close()
        second_session.close()
