from __future__ import annotations

import io
import shutil
import zipfile

from sqlalchemy import event

from app.extraction.manifests import DependencyManifestExtractor
from app.extraction.pipeline import ExtractionPipeline
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence.query_service import ARCHITECTURE_EVIDENCE_BATCH_SIZE, SnapshotQueryService
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models.repository import RepositoryRecord

from tests.analysis_helpers import run_analysis_jobs


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload(auth_client, files: dict[str, bytes], *, analyse: bool = True) -> dict:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("architecture.zip", _archive(files), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    # /start enqueues durably; draining the worker persists the legacy
    # intelligence the architecture read endpoints consume and seals a snapshot.
    # ``analyse=False`` leaves the job queued so a test can exercise the genuine
    # "no sealed snapshot yet" architecture response.
    assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
    if analyse:
        assert run_analysis_jobs() == 1
    return repository


def _persist_snapshot(
    repository_id: str,
    sources: dict[str, bytes],
    *,
    snapshot_sources: dict[str, bytes] | None = None,
    extra_unrendered_diagnostics: int = 0,
) -> str:
    from app.core.database import SessionLocal

    pipeline = ExtractionPipeline([TypeScriptExtractor(), DependencyManifestExtractor()])
    runs = pipeline.run(snapshot_sources or sources)
    producer_version_set = sorted({run.producer for run in runs} | {"relationship-resolver@1.0.0"})

    with SessionLocal() as session:
        repository = session.get(RepositoryRecord, repository_id)
        assert repository is not None
        store = SnapshotStore(session)
        snapshot = store.begin(
            repository_id=repository.id,
            revision=Revision(repository.revision_kind, repository.revision_value, repository.revision_ref),
            producer_version_set=producer_version_set,
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
            for diagnostic in run.result.diagnostics:
                store.add_diagnostic(
                    snapshot,
                    code=diagnostic.code,
                    category=diagnostic.category,
                    severity=diagnostic.severity,
                    message=diagnostic.message,
                    producer=run.producer,
                    path=diagnostic.path,
                    span=diagnostic.span,
                    subject=diagnostic.subject,
                    details=diagnostic.details,
                )
        RelationshipResolver(store).resolve(snapshot)
        for index in range(extra_unrendered_diagnostics):
            store.add_diagnostic(
                snapshot,
                code="RI-TS-PARSE",
                category="syntax extraction",
                severity="info",
                message=f"Irrelevant parser diagnostic {index}.",
                producer="relationship-resolver@1.0.0",
                path=f"src/generated/{index}.ts",
                span=(1, 1),
            )
        return store.seal(snapshot).snapshot_id


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


def test_architecture_edges_come_from_resolved_snapshot_evidence(auth_client):
    sources = {
        "README.md": b"# Architecture fixture\n",
        "package.json": b'{\n  "dependencies": {\n    "lodash": "4.17.21"\n  }\n}\n',
        "src/alpha/index.ts": (
            b"import { beta } from '../beta';\n"
            b"import { helper } from './util';\n"
            b"import React from 'react';\n"
            b"export const alpha = beta() + helper();\n"
        ),
        "src/alpha/util.ts": b"export function helper() { return 1; }\n",
        "src/beta/index.ts": b"export function beta() { return 1; }\n",
        "src/lonely/index.ts": b"export const lonely = 1;\n",
        "src/ambiguous/index.ts": b"import '../shared';\nexport const ambiguous = 1;\n",
        "src/unresolved/index.ts": b"import '../missing';\nexport const unresolved = 1;\n",
        "src/shared.ts": b"export const first = 1;\n",
        "src/shared.tsx": b"export const second = 2;\n",
        "src/alpha/package.json": b'{\n  "dependencies": {\n    "react": "18.3.0"\n  }\n}\n',
    }
    repository = _upload(auth_client, sources)
    snapshot_id = _persist_snapshot(repository["id"], sources)

    # Prove the architecture request consumes persisted metadata/snapshot facts,
    # not the repository working tree.
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        local_path = record.local_path
    shutil.rmtree(local_path)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture")
    assert response.status_code == 200, response.text
    architecture = response.json()
    nodes = {node["id"]: node for node in architecture["nodes"]}

    # Both modules have the same persisted role (entrypoint); neither is collapsed.
    assert "entrypoint" in nodes["module:alpha"]["tags"]
    assert "entrypoint" in nodes["module:beta"]["tags"]
    assert architecture["relationshipSnapshotId"] == snapshot_id

    import_edges = [
        edge
        for edge in architecture["edges"]
        if edge["source"] == "module:alpha"
        and edge["target"] == "module:beta"
        and edge["predicate"] == "imports"
    ]
    assert len(import_edges) == 1
    edge = import_edges[0]
    assert edge["truthClass"] == "inferred"
    assert edge["evidence"] == [
        {
            "snapshotId": snapshot_id,
            "factId": edge["evidence"][0]["factId"],
            "path": "src/alpha/index.ts",
            "startLine": 1,
            "endLine": 1,
        }
    ]
    assert "module:beta" in nodes["module:alpha"]["dependencies"]
    assert "module:alpha" in nodes["module:beta"]["dependents"]
    assert nodes["module:alpha"]["relationshipState"] == "connected"
    assert nodes["module:beta"]["relationshipState"] == "connected"
    assert any(
        item["source"] == "module:alpha"
        and item["target"] == "module:beta"
        and item["predicate"] == "calls"
        for item in architecture["edges"]
    )
    assert not any(item["source"] == item["target"] for item in architecture["edges"])
    assert not any(item["code"] == "ARCH-REL-ENDPOINT-UNMAPPED" for item in architecture["diagnostics"])

    dependency_edges = [
        item
        for item in architecture["edges"]
        if item["source"] == "module:alpha" and item["target"] == "dep:npm:react"
    ]
    assert {item["predicate"] for item in dependency_edges} == {"imports", "depends_on"}
    assert not any(item["target"] == "dep:npm:lodash" for item in architecture["edges"])
    assert "dep:npm:lodash" not in nodes
    assert "dep:npm:react" in nodes
    root_scope_diagnostic = next(
        item
        for item in architecture["diagnostics"]
        if item["code"] == "ARCH-REL-REPO-SCOPED"
        and item["path"] == "package.json"
        and item["severity"] == "info"
    )
    assert root_scope_diagnostic["nodeIds"] is None
    assert nodes["module:lonely"]["relationshipState"] == "no-observed-relationships"
    assert nodes["module:documentation"]["relationshipState"] == "not-extracted"

    diagnostics = architecture["diagnostics"]
    assert any(item["code"] == "RI-RES-AMBIGUOUS" and item["path"] == "src/ambiguous/index.ts" for item in diagnostics)
    assert any(item["code"] == "RI-RES-UNRESOLVED" and item["path"] == "src/unresolved/index.ts" for item in diagnostics)
    assert nodes["module:ambiguous"]["relationshipState"] == "unresolved"
    assert nodes["module:unresolved"]["relationshipState"] == "unresolved"
    assert not any(edge["source"] == "module:ambiguous" for edge in architecture["edges"])
    assert not any(edge["source"] == "module:unresolved" for edge in architecture["edges"])

    evidence_response = auth_client.get(f"/intelligence/v1/snapshots/{snapshot_id}/evidence?limit=100")
    assert evidence_response.status_code == 200
    assert any(
        item["factKind"] == "edge"
        and item["factId"] == edge["evidence"][0]["factId"]
        and item["path"] == edge["evidence"][0]["path"]
        and item["startLine"] == edge["evidence"][0]["startLine"]
        for item in evidence_response.json()["data"]
    )


def test_architecture_reports_resolved_facts_without_module_mapping(auth_client):
    sources = {
        "README.md": b"# Mapping fixture\n",
        "src/beta/index.ts": b"export function beta() { return 1; }\n",
    }
    repository = _upload(auth_client, sources)
    _persist_snapshot(
        repository["id"],
        sources,
        snapshot_sources={
            **sources,
            "unmapped.ts": b"import { beta } from './src/beta';\nexport const use = beta();\n",
        },
    )

    response = auth_client.get(f"/analysis/{repository['id']}/architecture")

    assert response.status_code == 200
    architecture = response.json()
    diagnostic = next(item for item in architecture["diagnostics"] if item["code"] == "ARCH-REL-ENDPOINT-UNMAPPED")
    assert diagnostic["subjectKey"] == "file:unmapped.ts"
    assert diagnostic["objectKey"] == "file:src/beta/index.ts"
    assert diagnostic["nodeIds"] == ["module:beta"]


def test_architecture_fact_query_excludes_irrelevant_large_snapshot_records(auth_client):
    """Architecture reads relationship facts, not every stored snapshot record."""

    sources = {
        "src/alpha/index.ts": b"import { beta } from '../beta';\nexport const alpha = beta;\n",
        "src/beta/index.ts": b"export function beta() { return 1; }\n",
    }
    snapshot_sources = {
        **sources,
        **{
            f"src/generated/{index}.ts": f"export const generated{index} = {index};\n".encode()
            for index in range(64)
        },
    }
    repository = _upload(auth_client, sources)
    _persist_snapshot(
        repository["id"],
        sources,
        snapshot_sources=snapshot_sources,
        extra_unrendered_diagnostics=64,
    )

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        module_paths = set(sources) | {f"src/untracked/{index}.ts" for index in range(1_000)}
        facts = SnapshotQueryService(session, record.owner_id).architecture_facts(
            record.id,
            module_paths=module_paths,
        )

    assert facts is not None
    assert [edge.predicate for edge in facts.edges] == ["imports"]
    assert {node.stable_key for node in facts.nodes} == {
        "file:src/alpha/index.ts",
        "file:src/beta/index.ts",
    }
    assert set(facts.node_evidence) == {node.id for node in facts.nodes}
    assert set(facts.edge_evidence) == {edge.id for edge in facts.edges}
    assert facts.diagnostics == []
    assert facts.covered_paths == set(sources)

    response = auth_client.get(f"/analysis/{repository['id']}/architecture")
    assert response.status_code == 200, response.text
    assert not any(item["code"] == "RI-TS-PARSE" for item in response.json()["diagnostics"])


def test_architecture_fact_query_batches_relevant_evidence_ids(auth_client):
    """Architecture evidence reads stay below the configured SQL parameter bound."""

    sources = {
        "src/target.ts": b"export const target = 1;\n",
        **{
            f"src/importers/{index}.ts": (
                b"import { target } from '../target';\n"
                + f"export const importer{index} = target;\n".encode()
            )
            for index in range(ARCHITECTURE_EVIDENCE_BATCH_SIZE + 1)
        },
    }
    repository = _upload(auth_client, sources, analyse=False)
    _persist_snapshot(repository["id"], sources)

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        record = session.get(RepositoryRecord, repository["id"])
        assert record is not None
        evidence_query_parameter_counts: list[int] = []

        def record_evidence_batch(_conn, _cursor, statement, parameters, _context, _executemany):
            if "FROM ri_evidence" not in statement:
                return
            if "ri_evidence.node_ref IN" not in statement and "ri_evidence.edge_ref IN" not in statement:
                return
            evidence_query_parameter_counts.append(len(parameters))

        event.listen(session.bind, "before_cursor_execute", record_evidence_batch)
        try:
            facts = SnapshotQueryService(session, record.owner_id).architecture_facts(
                record.id,
                module_paths=sources,
            )
        finally:
            event.remove(session.bind, "before_cursor_execute", record_evidence_batch)

    assert facts is not None
    assert len(facts.edges) == ARCHITECTURE_EVIDENCE_BATCH_SIZE + 1
    assert len(facts.nodes) == ARCHITECTURE_EVIDENCE_BATCH_SIZE + 2
    assert len(facts.node_evidence) == len(facts.nodes)
    assert len(facts.edge_evidence) == len(facts.edges)
    assert sorted(evidence_query_parameter_counts) == [
        2,
        3,
        ARCHITECTURE_EVIDENCE_BATCH_SIZE + 1,
        ARCHITECTURE_EVIDENCE_BATCH_SIZE + 1,
    ]
    assert max(evidence_query_parameter_counts) <= ARCHITECTURE_EVIDENCE_BATCH_SIZE + 1


def test_architecture_without_snapshot_does_not_claim_isolation(auth_client):
    # Leave the analysis job queued (worker not drained) so no snapshot is sealed:
    # this exercises the genuine "no sealed snapshot" architecture response, which
    # durable analysis otherwise reaches only in the window before the worker runs.
    repository = _upload(
        auth_client, {"src/lonely/index.ts": b"export const lonely = 1;\n"}, analyse=False
    )

    response = auth_client.get(f"/analysis/{repository['id']}/architecture")

    assert response.status_code == 200
    architecture = response.json()
    assert architecture["relationshipSnapshotId"] is None
    assert architecture["edges"] == []
    assert architecture["nodes"][0]["relationshipState"] == "not-extracted"
    assert architecture["diagnostics"] == [
        {
            "code": "ARCH-REL-NOT-EXTRACTED",
            "category": "relationship extraction",
            "severity": "info",
            "message": "No sealed repository-intelligence snapshot is available for relationship analysis.",
            "path": None,
            "startLine": None,
            "endLine": None,
            "subjectKey": None,
            "objectKey": None,
            "details": None,
            "nodeIds": None,
        }
    ]
