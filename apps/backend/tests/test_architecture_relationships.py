from __future__ import annotations

import io
import shutil
import zipfile

from app.extraction.manifests import DependencyManifestExtractor
from app.extraction.pipeline import ExtractionPipeline
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence.resolution import RelationshipResolver
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models.repository import RepositoryRecord


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload(auth_client, files: dict[str, bytes]) -> dict:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("architecture.zip", _archive(files), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
    return repository


def _persist_snapshot(
    repository_id: str,
    sources: dict[str, bytes],
    *,
    snapshot_sources: dict[str, bytes] | None = None,
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


def test_architecture_without_snapshot_does_not_claim_isolation(auth_client):
    repository = _upload(auth_client, {"src/lonely/index.ts": b"export const lonely = 1;\n"})

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
