from __future__ import annotations

import io
import zipfile
from urllib.parse import urlencode

from app.extraction.pipeline import ExtractionPipeline
from app.extraction.python import PythonExtractor
from app.intelligence.classification import RoleClassifier
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models.repository import RepositoryRecord
from app.models.snapshot import RiEvidence

from tests.analysis_helpers import run_analysis_jobs

_SOURCES = {
    "README.md": b"# evidence fixture\n",
    "src/routes.py": (
        b"from fastapi import FastAPI, Depends\n"
        b"from src.dependencies import get_current_user\n\n"
        b"app = FastAPI()\n\n\n"
        b'@app.get("/me")\n'
        b"def read_me(user=Depends(get_current_user)):\n"
        b"    return user\n"
    ),
    "src/dependencies.py": b"def get_current_user(token: str) -> str:\n    return token\n",
}
_ROUTE_FACT_ID = "src/routes.py::(anonymous:route#1)"


def _upload(auth_client, files: dict[str, bytes]) -> dict:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("evidence.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
    assert run_analysis_jobs() == 1
    return repository


def _evidence(item, extractor: str, version: str) -> Evidence:
    return Evidence(
        path=item.path,
        start_line=item.start_line,
        end_line=item.end_line,
        extractor=extractor,
        extractor_version=version,
        logical_line_count=item.logical_line_count,
        granularity=item.granularity,
    )


def _persist_snapshot(repository_id: str, sources: dict[str, bytes], *, schema_version: str | None = None) -> str:
    from app.core.database import SessionLocal

    pipeline = ExtractionPipeline([PythonExtractor()])
    runs = pipeline.run(sources)
    producer_version_set = sorted(
        {run.producer for run in runs}
        | {
            f"{RelationshipResolver.name}@{RelationshipResolver.version}",
            f"{RoleClassifier.name}@{RoleClassifier.version}",
        }
    )

    with SessionLocal() as session:
        repository = session.get(RepositoryRecord, repository_id)
        assert repository is not None
        store = SnapshotStore(session)
        begin_kwargs = {} if schema_version is None else {"schema_version": schema_version}
        snapshot = store.begin(
            repository_id=repository.id,
            revision=Revision(repository.revision_kind, repository.revision_value, repository.revision_ref),
            producer_version_set=producer_version_set,
            **begin_kwargs,
        )
        for run in runs:
            for node in run.result.nodes:
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
                    evidence=[_evidence(item, run.producer_name, run.producer_version) for item in node.evidence],
                )
            for observation in run.result.observations:
                store.add_observation(
                    snapshot,
                    observed_kind=observation.observed_kind,
                    subject_kind=observation.subject_kind,
                    subject_key=observation.subject_key,
                    referent_text=observation.referent_text,
                    ordinal=observation.ordinal,
                    evidence=_evidence(observation.evidence, run.producer_name, run.producer_version),
                )
        RelationshipResolver(store).resolve(snapshot)
        RoleClassifier(store).classify(snapshot)
        return store.seal(snapshot).snapshot_id


def _evidence_url(
    repository_id: str,
    snapshot_id: str,
    path: str,
    start_line: int,
    end_line: int,
    *,
    fact_id: str = _ROUTE_FACT_ID,
) -> str:
    return f"/analysis/{repository_id}/evidence?" + urlencode(
        {
            "snapshotId": snapshot_id,
            "factId": fact_id,
            "path": path,
            "startLine": start_line,
            "endLine": end_line,
        }
    )


def test_evidence_source_returns_exact_cited_revision_content(auth_client):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 7, 7))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "ready"
    assert body["snapshotId"] == snapshot_id
    assert body["factId"] == _ROUTE_FACT_ID
    assert body["revisionKind"] == "upload"
    assert body["revisionValue"] == repository["revision"]["value"]
    assert body["path"] == "src/routes.py"
    assert body["startLine"] == 7
    assert body["endLine"] == 7
    assert body["content"] is not None
    assert "def read_me" in body["content"]


def test_evidence_source_rejects_snapshot_from_another_repository(auth_client):
    repository_a = _upload(auth_client, _SOURCES)
    snapshot_a = _persist_snapshot(repository_a["id"], _SOURCES)
    repository_b = _upload(auth_client, {"README.md": b"# other\n", "src/plain.py": b"x = 1\n"})

    response = auth_client.get(_evidence_url(repository_b["id"], snapshot_a, "src/routes.py", 7, 7))
    assert response.status_code == 404


def test_evidence_source_is_owner_scoped(auth_client, make_auth_headers):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    other = make_auth_headers("other-owner@example.com")
    response = auth_client.get(
        _evidence_url(repository["id"], snapshot_id, "src/routes.py", 7, 7),
        headers=other["headers"],
    )
    assert response.status_code == 404


def test_evidence_source_checks_owner_before_required_query_validation(auth_client, make_auth_headers):
    repository = _upload(auth_client, _SOURCES)

    other = make_auth_headers("other-owner-validation@example.com")
    response = auth_client.get(
        f"/analysis/{repository['id']}/evidence",
        headers=other["headers"],
        params={"path": "src/routes.py"},
    )
    assert response.status_code == 404


def test_evidence_source_rejects_unrecognized_snapshot(auth_client):
    repository = _upload(auth_client, _SOURCES)
    response = auth_client.get(_evidence_url(repository["id"], "snap_does_not_exist", "src/routes.py", 7, 7))
    assert response.status_code == 404


def test_evidence_source_rejects_unsealed_snapshot(auth_client):
    from app.core.database import SessionLocal

    repository = _upload(auth_client, _SOURCES)
    pipeline = ExtractionPipeline([PythonExtractor()])
    runs = pipeline.run(_SOURCES)

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        store = SnapshotStore(session)
        snapshot = store.begin(
            repository_id=record.id,
            revision=Revision(record.revision_kind, record.revision_value, record.revision_ref),
            producer_version_set=sorted({run.producer for run in runs}),
        )
        for run in runs:
            for node in run.result.nodes:
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
                    evidence=[_evidence(item, run.producer_name, run.producer_version) for item in node.evidence],
                )
        building_snapshot_id = snapshot.snapshot_id
        # Deliberately never sealed: `state` remains "building".

    response = auth_client.get(_evidence_url(repository["id"], building_snapshot_id, "src/routes.py", 1, 1))
    assert response.status_code == 404


def test_evidence_source_rejects_unsupported_schema_version(auth_client):
    repository = _upload(auth_client, _SOURCES)
    # An unsupported schema version is set at snapshot construction time (the
    # only legitimate way it could ever arise -- e.g. after a future schema
    # migration), not by mutating an already-sealed snapshot: sealed rows are
    # immutable through both the ORM and a dedicated bulk-mutation guard.
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES, schema_version="ri.v99")

    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 7, 7))
    assert response.status_code == 422


def test_repository_revision_and_its_sealed_snapshots_cannot_diverge(auth_client):
    """The revision-mismatch state ``EvidenceSourceService`` defends against
    is not reachable in this schema: ``fk_ri_snapshots_repository_revision``
    is a composite foreign key from ``ri_snapshots(repository_id,
    revision_kind, revision_value)`` to ``repositories(id, revision_kind,
    revision_value)``, so the database itself refuses to let a repository's
    revision change out from under a snapshot that cites it. This proves the
    invariant at its strongest layer; ``EvidenceSourceService`` still checks
    it explicitly as defense-in-depth (e.g. for a future schema that relaxes
    this constraint), which is why the check remains in the service even
    though this test cannot force it to trigger through the live API."""

    import pytest
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    from app.core.database import SessionLocal

    repository = _upload(auth_client, _SOURCES)
    _persist_snapshot(repository["id"], _SOURCES)

    with SessionLocal() as session:
        # A Core-level statement bypasses the ORM's own immutable-revision
        # validator (which would otherwise raise first) so the underlying
        # database constraint itself is what is being proven here. SQLite
        # enforces the foreign key immediately, at statement-execution time.
        with pytest.raises(SAIntegrityError):
            session.execute(
                update(RepositoryRecord)
                .where(RepositoryRecord.id == repository["id"])
                .values(revision_value="sha256:" + "f" * 64)
            )
            session.commit()


def test_evidence_source_reports_unavailable_when_path_not_in_snapshot(auth_client):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/never_extracted.py", 1, 1))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["content"] is None


def test_evidence_source_reports_unavailable_for_forged_in_range_span(auth_client):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    # The path is genuine and this line exists, but (3, 3) is not one of the
    # exact evidence spans persisted for src/routes.py. A manipulated link
    # must not receive a verified badge for arbitrary source on a cited path.
    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 3, 3))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["content"] is None


def test_evidence_source_reports_unavailable_when_fact_id_does_not_match_span(auth_client):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    response = auth_client.get(
        _evidence_url(
            repository["id"],
            snapshot_id,
            "src/routes.py",
            7,
            7,
            fact_id="src/routes.py::read_me",
        )
    )
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["content"] is None


def test_evidence_source_rejects_path_traversal(auth_client):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "../../../etc/passwd", 1, 1))
    # Whether caught by the evidence-membership check or the filesystem
    # traversal guard, the exact file content must never be exposed as ready.
    if response.status_code == 200:
        assert response.json()["status"] == "unavailable"
    else:
        assert response.status_code == 422


def test_evidence_source_second_layer_rejects_a_maliciously_stored_traversal_path(auth_client):
    """Defense in depth: even if a bad path were ever stored as real evidence,
    the filesystem-level traversal guard in ``RepositoryService.read_file``
    must still refuse to serve it."""

    from sqlalchemy import insert, select

    from app.core.database import SessionLocal
    from app.models.snapshot import RiNode

    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    with SessionLocal() as session:
        any_node = session.scalars(select(RiNode).where(RiNode.snapshot_id == snapshot_id).limit(1)).one()
        # A sealed snapshot's facts are immutable through the ORM by design;
        # a Core-level statement simulates a corrupted/malicious evidence row
        # bypassing the extractor's own path normalization, purely to prove
        # the independent filesystem-level guard still holds even if the
        # evidence-membership check were ever fooled. Attached to a real node
        # so only ``path`` is adversarial -- everything else about the row is
        # a structurally valid evidence record.
        session.execute(
            insert(RiEvidence).values(
                snapshot_id=snapshot_id,
                node_ref=any_node.id,
                edge_ref=None,
                observation_ref=None,
                path="../../../etc/passwd",
                start_line=1,
                end_line=1,
                logical_line_count=1,
                granularity="span",
                extractor="test",
                extractor_version="1.0.0",
            )
        )
        session.commit()

    response = auth_client.get(
        _evidence_url(
            repository["id"],
            snapshot_id,
            "../../../etc/passwd",
            1,
            1,
            fact_id=any_node.stable_key,
        )
    )
    assert response.status_code == 422


def test_evidence_source_rejects_invalid_line_range(auth_client):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    zero_start = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 0, 1))
    assert zero_start.status_code == 422

    end_before_start = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 5, 2))
    assert end_before_start.status_code == 422


def test_evidence_source_reports_unavailable_for_out_of_range_span(auth_client):
    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 1, 10_000))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["content"] is None


def test_evidence_source_reports_unavailable_when_source_deleted(auth_client):
    import shutil

    from app.core.database import SessionLocal

    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        local_path = record.local_path
    shutil.rmtree(local_path)

    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 7, 7))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["content"] is None


def test_evidence_source_reports_unavailable_when_source_bytes_change(auth_client):
    from pathlib import Path

    from app.core.database import SessionLocal

    repository = _upload(auth_client, _SOURCES)
    snapshot_id = _persist_snapshot(repository["id"], _SOURCES)

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        source_path = Path(record.local_path) / "src/routes.py"
    source_path.write_text(
        _SOURCES["src/routes.py"].decode("utf-8").replace('"/me"', '"/mutated"'),
        encoding="utf-8",
    )

    response = auth_client.get(_evidence_url(repository["id"], snapshot_id, "src/routes.py", 7, 7))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["content"] is None
    assert "do not match" in body["reason"]
