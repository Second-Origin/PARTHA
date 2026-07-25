"""Regression coverage for #156: multi-manifest dependencies must not fail sealing.

``SnapshotStore.add_node`` rejects a second write for a stable key whose
``properties`` differ from the first. ``DependencyManifestExtractor`` embeds
per-declaration facts (``manifest_path``, ``version``, ...) straight into a
dependency node's ``properties``, so the same dependency name declared in more
than one manifest used to fail the entire analysis job. ``AnalysisWorker``
now merges same-producer dependency nodes sharing a stable key into one node
with a ``declarations`` list before persistence.
"""

from __future__ import annotations

import io
import json
import zipfile

from sqlalchemy import select

from app.core.database import SessionLocal
from app.extraction.base import ExtractedEvidence, ExtractedNode, ExtractionResult
from app.extraction.pipeline import ProducedExtraction
from app.models.snapshot import RiEdge, RiEvidence, RiNode, RiSnapshot
from app.workers.analysis_worker import AnalysisWorker
from tests.analysis_helpers import run_analysis_jobs

_PRODUCER = ("dependency-manifest", "1.2.0")


def _node(stable_key: str, *, name: str, manifest_path: str, version: str, dependency_type: str = "production", line: int = 1) -> ExtractedNode:
    return ExtractedNode(
        node_kind="dependency",
        stable_key=stable_key,
        name=name,
        language=None,
        evidence=(ExtractedEvidence(path=manifest_path, start_line=line, end_line=line, logical_line_count=max(line, 1)),),
        properties={
            "ecosystem": stable_key.split(":")[1],
            "version": version,
            "dependency_type": dependency_type,
            "manifest_path": manifest_path,
            "workspace_path": manifest_path.rsplit("/", 1)[0] if "/" in manifest_path else ".",
        },
    )


def _produced(*nodes: ExtractedNode, producer: tuple[str, str] = _PRODUCER) -> ProducedExtraction:
    return ProducedExtraction(producer[0], producer[1], ExtractionResult(nodes=tuple(nodes)))


# --- Unit coverage of the merge itself --------------------------------------


def test_merge_combines_declarations_from_two_manifests():
    produced = (
        _produced(_node("dep:npm:react", name="react", manifest_path="apps/frontend/package.json", version="^18.3.0")),
        _produced(_node("dep:npm:react", name="react", manifest_path="apps/admin/package.json", version="^18.3.0")),
    )

    merged = AnalysisWorker._merge_dependency_declarations(produced)

    dependency_nodes = [node for item in merged for node in item.result.nodes if node.node_kind == "dependency"]
    assert len(dependency_nodes) == 1
    node = dependency_nodes[0]
    assert node.stable_key == "dep:npm:react"
    assert len(node.evidence) == 2
    assert {declaration["manifest_path"] for declaration in node.properties["declarations"]} == {
        "apps/frontend/package.json",
        "apps/admin/package.json",
    }


def test_merge_preserves_conflicting_versions_rather_than_dropping_one():
    produced = (
        _produced(_node("dep:pypi:requests", name="requests", manifest_path="apps/backend/pyproject.toml", version="==2.31.0")),
        _produced(_node("dep:pypi:requests", name="requests", manifest_path="services/worker/requirements.txt", version=">=2.32")),
    )

    merged = AnalysisWorker._merge_dependency_declarations(produced)

    node = next(node for item in merged for node in item.result.nodes if node.node_kind == "dependency")
    versions = {declaration["version"] for declaration in node.properties["declarations"]}
    assert versions == {"==2.31.0", ">=2.32"}


def test_merge_combines_two_sections_of_the_same_manifest_file():
    produced = (
        _produced(
            _node("dep:npm:lodash", name="lodash", manifest_path="package.json", version="^4.17.21", dependency_type="production"),
            _node("dep:npm:lodash", name="lodash", manifest_path="package.json", version="^4.17.21", dependency_type="development", line=2),
        ),
    )

    merged = AnalysisWorker._merge_dependency_declarations(produced)

    node = next(node for item in merged for node in item.result.nodes if node.node_kind == "dependency")
    types = {declaration["dependency_type"] for declaration in node.properties["declarations"]}
    assert types == {"production", "development"}


def test_merge_is_a_no_op_for_a_single_declaration_shape():
    produced = (_produced(_node("dep:npm:react", name="react", manifest_path="package.json", version="^18.3.0")),)

    merged = AnalysisWorker._merge_dependency_declarations(produced)

    node = next(node for item in merged for node in item.result.nodes if node.node_kind == "dependency")
    assert node.properties["declarations"] == [
        {
            "name": "react",
            "version": "^18.3.0",
            "dependency_type": "production",
            "manifest_path": "package.json",
            "workspace_path": ".",
            "start_line": 1,
            "end_line": 1,
            "extractor": "dependency-manifest",
            "extractor_version": "1.2.0",
        }
    ]


def test_merge_leaves_non_dependency_nodes_untouched():
    file_node = ExtractedNode(
        node_kind="file",
        stable_key="file:src/app.py",
        name="app.py",
        language="python",
        evidence=(ExtractedEvidence(path="src/app.py", start_line=1, end_line=1, logical_line_count=1),),
    )
    produced = (ProducedExtraction("python-extractor", "1.0.0", ExtractionResult(nodes=(file_node,))),)

    merged = AnalysisWorker._merge_dependency_declarations(produced)

    assert merged == produced


def test_merge_leaves_a_cross_producer_stable_key_collision_unmerged():
    """A different producer disagreeing about the same key is a real conflict.

    This case does not arise from today's extractors, but the merge must not
    paper over it if it ever does: leaving it untouched preserves
    ``SnapshotStore.add_node``'s existing conflict rejection for a genuine
    identity disagreement, as opposed to an ordinary multi-manifest
    declaration from the same producer.
    """

    produced = (
        _produced(_node("dep:npm:react", name="react", manifest_path="package.json", version="^18.3.0")),
        _produced(
            _node("dep:npm:react", name="react", manifest_path="other.json", version="^18.3.0"),
            producer=("other-extractor", "9.9.9"),
        ),
    )

    merged = AnalysisWorker._merge_dependency_declarations(produced)

    assert merged == produced


# --- End-to-end coverage through the real analysis pipeline -----------------


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _upload_and_analyse(auth_client, sources: dict[str, bytes]) -> str:
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("repo.zip", _archive(sources), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository_id = response.json()["id"]
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200
    assert run_analysis_jobs() == 1
    return repository_id


def test_a_dependency_declared_in_two_manifests_still_seals_a_snapshot(auth_client):
    repository_id = _upload_and_analyse(
        auth_client,
        {
            "README.md": b"# repo\n",
            "apps/backend/pyproject.toml": b'[project]\ndependencies = [\n  "requests==2.31.0",\n]\n',
            "services/worker/requirements.txt": b"requests>=2.32\n",
        },
    )

    with SessionLocal() as session:
        snapshot = session.scalars(select(RiSnapshot).where(RiSnapshot.repository_id == repository_id)).first()
        assert snapshot is not None
        assert snapshot.state == "completed"
        assert snapshot.canonical_graph_hash is not None

        node = session.scalars(
            select(RiNode).where(RiNode.snapshot_id == snapshot.snapshot_id, RiNode.stable_key == "dep:pypi:requests")
        ).first()
        assert node is not None
        versions = {declaration["version"] for declaration in node.properties["declarations"]}
        assert versions == {"==2.31.0", ">=2.32"}

        edge = session.scalars(
            select(RiEdge).where(
                RiEdge.snapshot_id == snapshot.snapshot_id,
                RiEdge.subject_key == "repo:root",
                RiEdge.predicate == "depends_on",
                RiEdge.object_key == "dep:pypi:requests",
            )
        ).first()
        assert edge is not None
        edge_evidence = session.scalars(
            select(RiEvidence).where(RiEvidence.snapshot_id == snapshot.snapshot_id, RiEvidence.edge_ref == edge.id)
        ).all()
        assert {item.path for item in edge_evidence} == {
            "apps/backend/pyproject.toml",
            "services/worker/requirements.txt",
        }


def test_analysis_and_sealed_snapshot_surfaces_recover_once_sealed(auth_client):
    repository_id = _upload_and_analyse(
        auth_client,
        {
            "README.md": b"# repo\n",
            "apps/frontend/package.json": json.dumps({"dependencies": {"react": "^18.3.0"}}).encode(),
            "apps/admin/package.json": json.dumps({"dependencies": {"react": "^18.3.0"}}).encode(),
        },
    )

    status = auth_client.get(f"/analysis/{repository_id}/status").json()
    assert status["status"] == "completed", status

    architecture = auth_client.get(f"/analysis/{repository_id}/architecture")
    assert architecture.status_code == 200, architecture.text

    review = auth_client.get(f"/analysis/{repository_id}/review")
    assert review.status_code == 200, review.text

    insights = auth_client.get(f"/analysis/{repository_id}/insights")
    assert insights.status_code == 200, insights.text
    assert insights.json()["metrics"][2]["id"] == "nodes.dependencies.total"
    assert insights.json()["metrics"][2]["value"] == 1
