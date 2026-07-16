from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.python import PythonExtractor
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
        end_line=extracted.end_line, extractor="python-ast",
        extractor_version="1.0.0", logical_line_count=extracted.logical_line_count,
        granularity=extracted.granularity,
    )


def test_python_extraction_result_seals_into_a_snapshot(session):
    repository = _repository(session)
    result = PythonExtractor().extract(
        "app/api/auth.py",
        b"import os\n\n\ndef get_current_user():\n    return None\n",
    )
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=["python-ast@1.0.0"],
    )
    # a repo:root node is required for a coherent snapshot (RFC §11.2 rule 5)
    root_ev = Evidence(
        path="app/api/auth.py", start_line=1, end_line=1,
        extractor="python-ast", extractor_version="1.0.0",
        logical_line_count=5, granularity="file",
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
            message=diag.message, producer="python-ast@1.0.0", path=diag.path,
            span=diag.span, subject=diag.subject, details=diag.details,
        )

    sealed = store.seal(snapshot)
    assert sealed.state == "completed"
    assert sealed.canonical_graph_hash.startswith("sha256:")
