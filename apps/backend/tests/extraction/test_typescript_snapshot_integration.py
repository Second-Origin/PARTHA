from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base

UPLOAD_REVISION = "sha256:" + "a" * 64


@pytest.fixture()
def session(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'snap.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()


def _repository(session: Session) -> RepositoryRecord:
    owner = User(id=str(uuid4()), email="o@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    record = RepositoryRecord(
        id=str(uuid4()), owner_id=owner.id, name="repo", source="upload",
        revision_kind="upload", revision_value=UPLOAD_REVISION,
        local_path="/x", status="completed", file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def _to_evidence(extracted) -> Evidence:
    return Evidence(
        path=extracted.path, start_line=extracted.start_line,
        end_line=extracted.end_line, extractor="typescript-ast",
        extractor_version="1.1.0", logical_line_count=extracted.logical_line_count,
        granularity=extracted.granularity,
    )


def test_typescript_extraction_result_seals_into_a_snapshot(session):
    repository = _repository(session)
    result = TypeScriptExtractor().extract(
        "src/auth/service.ts",
        b"export function issueToken() {\n  return 1;\n}\n",
    )
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=["typescript-ast@1.1.0"],
    )
    # a repo:root node is required for a coherent snapshot (RFC §11.2 rule 5)
    root_ev = Evidence(
        path="src/auth/service.ts", start_line=1, end_line=1,
        extractor="typescript-ast", extractor_version="1.1.0",
        logical_line_count=1, granularity="file",
    )
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[root_ev])
    for node in result.nodes:
        store.add_node(
            snapshot, node_kind=node.node_kind, stable_key=node.stable_key,
            name=node.name, language=node.language,
            properties=node.properties,
            evidence=[_to_evidence(e) for e in node.evidence],
        )
    for obs in result.observations:
        store.add_observation(
            snapshot, observed_kind=obs.observed_kind, subject_kind=obs.subject_kind,
            subject_key=obs.subject_key, referent_text=obs.referent_text,
            ordinal=obs.ordinal, evidence=_to_evidence(obs.evidence),
        )
    for diag in result.diagnostics:
        store.add_diagnostic(
            snapshot, code=diag.code, category=diag.category, severity=diag.severity,
            message=diag.message, producer="typescript-ast@1.1.0", path=diag.path,
            span=diag.span, subject=diag.subject, details=diag.details,
        )

    sealed = store.seal(snapshot)
    assert sealed.state == "completed"
    assert sealed.canonical_graph_hash.startswith("sha256:")


def test_sibling_typescript_files_seal_into_one_snapshot(session):
    # The module node is directory-scoped, so sibling files must produce an
    # identical module record rather than a conflicting one.
    repository = _repository(session)
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=["typescript-ast@1.1.0"],
    )
    store.add_node(
        snapshot, node_kind="repository", stable_key="repo:root",
        evidence=[Evidence(
            path="src/auth/service.ts", start_line=1, end_line=1,
            extractor="typescript-ast", extractor_version="1.1.0",
            logical_line_count=1, granularity="file",
        )],
    )
    extractor = TypeScriptExtractor()
    files = {
        "src/auth/service.ts": b"export function issueToken() {\n  return 1;\n}\n",
        "src/auth/tokens.ts": b"import { issueToken } from './service';\nexport const t = 1;\n",
    }
    for path, source in files.items():
        result = extractor.extract(path, source)
        for node in result.nodes:
            store.add_node(
                snapshot, node_kind=node.node_kind, stable_key=node.stable_key,
                name=node.name, language=node.language, properties=node.properties,
                evidence=[_to_evidence(e) for e in node.evidence],
            )
        for obs in result.observations:
            store.add_observation(
                snapshot, observed_kind=obs.observed_kind, subject_kind=obs.subject_kind,
                subject_key=obs.subject_key, referent_text=obs.referent_text,
                ordinal=obs.ordinal, evidence=_to_evidence(obs.evidence),
            )

    sealed = store.seal(snapshot)
    assert sealed.state == "completed"
