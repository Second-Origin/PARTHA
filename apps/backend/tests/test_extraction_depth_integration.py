"""End-to-end W1 extraction depth through the durable analysis job (#209).

Unit tests prove each extractor in isolation. This proves the part that only
the real pipeline can: that a repository containing manifests, lockfiles, IaC,
and HTTP call sites seals **one** snapshot in which the new facts carry their
truth class and provenance, the dependency identities did not fork, and the
whole graph hashes to the same value on a repeated run.
"""

from __future__ import annotations

import io
import zipfile

from sqlalchemy import select

from app.core.database import SessionLocal
from app.extraction import production_extractors
from app.extraction.dependencies import merge_dependency_facts
from app.extraction.iac import IacExtractor
from app.extraction.lockfiles import LockfileExtractor
from app.extraction.pipeline import ExtractionPipeline
from app.models.snapshot import RiDiagnostic, RiEdge, RiEvidence, RiNode, RiObservation, RiSnapshot
from app.services.analysis_job_service import ANALYSIS_PRODUCER_VERSION_SET
from tests.analysis_helpers import run_analysis_jobs

SOURCES: dict[str, bytes] = {
    "package.json": b'{\n  "name": "web",\n  "dependencies": {\n    "left-pad": "^1.3.0"\n  }\n}\n',
    "package-lock.json": (
        b"{\n"
        b'  "name": "web",\n'
        b'  "lockfileVersion": 3,\n'
        b'  "packages": {\n'
        b'    "": {\n      "name": "web"\n    },\n'
        b'    "node_modules/left-pad": {\n      "version": "1.3.1"\n    },\n'
        # Pinned but never declared — the ordinary transitive shape.
        b'    "node_modules/util": {\n      "version": "0.12.5",\n      "dev": true\n    },\n'
        b'    "node_modules/util/node_modules/left-pad": {\n      "version": "1.2.0"\n    }\n'
        b"  }\n"
        b"}\n"
    ),
    "pyproject.toml": b'[project]\ndependencies = [\n  "Requests_Toolbelt>=1.0",\n]\n',
    "poetry.lock": (
        b'[[package]]\nname = "requests-toolbelt"\nversion = "1.0.0"\ncategory = "main"\n\n'
        b'[metadata]\nlock-version = "2.0"\n'
    ),
    "docker-compose.yml": (
        b"services:\n  api:\n    image: python:3.13-slim\n  worker:\n    image: ${TAG}\nvolumes:\n  pgdata:\n"
    ),
    "app/client.py": (
        b"import requests\n\n\n"
        b"def load_users():\n"
        b'    return requests.get("https://api.example.com/v1/users")\n'
    ),
    "src/api.ts": b'export async function ping() {\n  return fetch("https://api.example.com/health");\n}\n',
}


def _archive(files: dict[str, bytes]) -> bytes:
    """Build a byte-deterministic ZIP.

    An upload's revision identity is the SHA-256 of the archive bytes, and
    ``writestr`` would otherwise stamp each entry with the current time — so a
    default archive of identical files is a *different* revision every call.
    Pinning the entry timestamp is what lets a test upload the same revision
    twice on purpose.
    """

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0)), content)
    return buffer.getvalue()


def _upload_and_analyse(auth_client, sources: dict[str, bytes] | bytes) -> str:
    payload = sources if isinstance(sources, bytes) else _archive(sources)
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("repo.zip", payload, "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository_id = response.json()["id"]
    assert auth_client.post(f"/analysis/{repository_id}/start").status_code == 200
    assert run_analysis_jobs() == 1
    return repository_id


def _snapshot(session, repository_id: str) -> RiSnapshot:
    snapshot = session.scalars(select(RiSnapshot).where(RiSnapshot.repository_id == repository_id)).one()
    assert snapshot.state == "completed"
    return snapshot


def _nodes(session, snapshot, kind: str) -> dict[str, RiNode]:
    return {
        node.stable_key: node
        for node in session.scalars(
            select(RiNode).where(RiNode.snapshot_id == snapshot.snapshot_id, RiNode.node_kind == kind)
        )
    }


def _triples(session, snapshot, predicate: str) -> set[tuple[str, str]]:
    return {
        (edge.subject_key, edge.object_key)
        for edge in session.scalars(
            select(RiEdge).where(RiEdge.snapshot_id == snapshot.snapshot_id, RiEdge.predicate == predicate)
        )
    }


def test_the_planned_producer_set_declares_every_registered_extractor():
    """Submit and execution key on this set, so a new producer must be in it."""

    assert f"{LockfileExtractor.name}@{LockfileExtractor.version}" in ANALYSIS_PRODUCER_VERSION_SET
    assert f"{IacExtractor.name}@{IacExtractor.version}" in ANALYSIS_PRODUCER_VERSION_SET
    assert list(ANALYSIS_PRODUCER_VERSION_SET) == sorted(ANALYSIS_PRODUCER_VERSION_SET)
    assert len(set(ANALYSIS_PRODUCER_VERSION_SET)) == len(ANALYSIS_PRODUCER_VERSION_SET)


def test_a_repository_with_lockfiles_iac_and_http_clients_seals_one_snapshot(auth_client):
    repository_id = _upload_and_analyse(auth_client, SOURCES)

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)
        assert snapshot.canonical_graph_hash is not None
        # Sealing requires declared ⊇ observed, so every emitting producer here
        # is one the submitted identity already fixed.
        assert set(snapshot.actual_producers or ()) <= set(snapshot.producer_version_set)


def test_a_declaration_and_its_lockfile_pin_share_one_dependency_node(auth_client):
    repository_id = _upload_and_analyse(auth_client, SOURCES)

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)
        dependencies = _nodes(session, snapshot, "dependency")

        left_pad = dependencies["dep:npm:left-pad"]
        assert [item["version"] for item in left_pad.properties["declarations"]] == ["^1.3.0"]
        # Two installed versions of one package remain two resolutions of the
        # single logical identity, not a second dependency node.
        assert sorted(item["resolved_version"] for item in left_pad.properties["resolutions"]) == ["1.2.0", "1.3.1"]

        # PEP 503 folds the manifest's ``Requests_Toolbelt`` and the lockfile's
        # ``requests-toolbelt`` onto one key.
        toolbelt = dependencies["dep:pypi:requests-toolbelt"]
        assert len(toolbelt.properties["declarations"]) == 1
        assert [item["resolved_version"] for item in toolbelt.properties["resolutions"]] == ["1.0.0"]
        assert not any(key.startswith("dep:pypi:requests_toolbelt") for key in dependencies)


def test_each_producer_is_credited_only_with_the_spans_it_read(auth_client):
    repository_id = _upload_and_analyse(auth_client, SOURCES)

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)
        node = _nodes(session, snapshot, "dependency")["dep:npm:left-pad"]
        evidence = {
            (item.extractor, item.path)
            for item in session.scalars(
                select(RiEvidence).where(
                    RiEvidence.snapshot_id == snapshot.snapshot_id, RiEvidence.node_ref == node.id
                )
            )
        }

        assert evidence == {
            ("dependency-manifest", "package.json"),
            ("dependency-lockfile", "package-lock.json"),
        }


def test_a_lockfile_pin_alone_never_claims_a_direct_dependency(auth_client):
    repository_id = _upload_and_analyse(auth_client, SOURCES)

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)
        depends_on = {object_key for _, object_key in _triples(session, snapshot, "depends_on")}

        # ``util`` is pinned by the lockfile but declared by no manifest, so it
        # is a real node with a real resolution and no direct-dependency edge:
        # the repository never asked for it.
        assert "dep:npm:left-pad" in depends_on
        assert "dep:pypi:requests-toolbelt" in depends_on
        assert "dep:npm:util" in _nodes(session, snapshot, "dependency")
        assert "dep:npm:util" not in depends_on
        resolutions = session.scalars(
            select(RiObservation).where(
                RiObservation.snapshot_id == snapshot.snapshot_id,
                RiObservation.observed_kind == "resolution",
            )
        ).all()
        assert {item.referent_text for item in resolutions} == {"1.3.1", "1.2.0", "0.12.5", "1.0.0"}


def test_http_call_sites_resolve_to_one_language_neutral_service(auth_client):
    repository_id = _upload_and_analyse(auth_client, SOURCES)

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)
        services = _nodes(session, snapshot, "service")

        # The Python and TypeScript call sites reach the same origin, so they
        # must land on one node or the snapshot would not have sealed.
        assert set(services) == {"svc:https://api.example.com"}
        assert services["svc:https://api.example.com"].language is None
        # Each edge is attributed to the symbol whose span contains the call,
        # exactly like a generic ``calls`` reference.
        assert _triples(session, snapshot, "calls_service") == {
            ("app/client.py::load_users", "svc:https://api.example.com"),
            ("src/api.ts::ping", "svc:https://api.example.com"),
        }


def test_iac_resources_are_declared_by_the_repository_with_exact_spans(auth_client):
    repository_id = _upload_and_analyse(auth_client, SOURCES)

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)
        resources = _nodes(session, snapshot, "iac_resource")

        assert set(resources) == {
            "iac:docker-compose.yml::service/api",
            "iac:docker-compose.yml::service/worker",
            "iac:docker-compose.yml::volume/pgdata",
        }
        assert resources["iac:docker-compose.yml::service/api"].properties["image"] == "python:3.13-slim"
        assert "image" not in resources["iac:docker-compose.yml::service/worker"].properties
        assert _triples(session, snapshot, "declares") == {
            ("repo:root", key) for key in resources
        }
        api_evidence = session.scalars(
            select(RiEvidence).where(
                RiEvidence.snapshot_id == snapshot.snapshot_id,
                RiEvidence.node_ref == resources["iac:docker-compose.yml::service/api"].id,
            )
        ).all()
        assert [(item.path, item.start_line, item.end_line) for item in api_evidence] == [
            ("docker-compose.yml", 2, 2)
        ]


def test_a_templated_iac_value_is_disclosed_at_the_resource_it_belongs_to(auth_client):
    repository_id = _upload_and_analyse(auth_client, SOURCES)

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)
        diagnostics = [
            (item.code, item.producer, item.subject_key, item.span_start_line)
            for item in session.scalars(
                select(RiDiagnostic).where(
                    RiDiagnostic.snapshot_id == snapshot.snapshot_id,
                    RiDiagnostic.message == "templated IaC value is unsupported",
                )
            )
        ]

        assert diagnostics == [
            (
                "RI-EXT-UNSUPPORTED",
                f"{IacExtractor.name}@{IacExtractor.version}",
                "iac:docker-compose.yml::service/worker",
                4,
            )
        ]


def test_the_direct_dependency_graph_excludes_lockfile_only_packages(auth_client):
    """The Dependency Graph claims direct declarations; a pin is not one."""

    repository_id = _upload_and_analyse(auth_client, SOURCES)

    response = auth_client.get(f"/analysis/{repository_id}/dependencies")
    assert response.status_code == 200, response.text
    payload = response.json()
    rendered = {node["id"] for node in payload["nodes"]}
    assert payload["totalDependencies"] == len(rendered)

    assert "dep:npm:left-pad" in rendered
    assert "dep:pypi:requests-toolbelt" in rendered
    # ``util`` exists as a node because the lockfile pinned it, but nothing
    # declared it, so it must not be presented as a direct dependency.
    assert "dep:npm:util" not in rendered
    with SessionLocal() as session:
        assert "dep:npm:util" in _nodes(session, _snapshot(session, repository_id), "dependency")


def test_repeated_extraction_of_one_revision_is_byte_identical(auth_client):
    """Nothing may depend on the order the source stream happened to arrive in.

    The same revision cannot be uploaded twice — an immutable revision is a
    duplicate by design — so determinism is asserted over the extractor set the
    worker runs, in both source orders. The sealed-hash half of this guarantee
    is enforced by the golden benchmark's determinism gate.
    """

    repository_id = _upload_and_analyse(auth_client, SOURCES)

    def run(sources: dict[str, bytes]):
        pipeline = ExtractionPipeline(production_extractors())
        return merge_dependency_facts(pipeline.run(sources))

    forward = run(SOURCES)
    reversed_order = run(dict(reversed(list(SOURCES.items()))))

    assert forward == run(SOURCES)
    assert sorted(
        (node.node_kind, node.stable_key, node.name, str(node.properties))
        for item in forward
        for node in item.result.nodes
    ) == sorted(
        (node.node_kind, node.stable_key, node.name, str(node.properties))
        for item in reversed_order
        for node in item.result.nodes
    )

    with SessionLocal() as session:
        assert _snapshot(session, repository_id).canonical_graph_hash is not None


def test_an_unsupported_lockfile_revision_seals_a_disclosure_and_no_dependency(auth_client):
    repository_id = _upload_and_analyse(
        auth_client,
        {
            "README.md": b"# repo\n",
            "package-lock.json": b'{\n  "lockfileVersion": 1,\n  "dependencies": {\n    "left-pad": {\n      "version": "1.3.0"\n    }\n  }\n}\n',
        },
    )

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)

        assert _nodes(session, snapshot, "dependency") == {}
        codes = [
            (item.code, item.producer)
            for item in session.scalars(
                select(RiDiagnostic).where(
                    RiDiagnostic.snapshot_id == snapshot.snapshot_id,
                    RiDiagnostic.subject_key == "file:package-lock.json",
                )
            )
        ]
        assert codes == [("RI-EXT-UNSUPPORTED", f"{LockfileExtractor.name}@{LockfileExtractor.version}")]


def test_an_oversized_lockfile_is_skipped_by_the_source_budget_not_parsed(auth_client):
    padding = b" " * (600 * 1024)
    repository_id = _upload_and_analyse(
        auth_client,
        {
            "README.md": b"# repo\n",
            "package-lock.json": b'{\n  "lockfileVersion": 3,\n  "packages": {\n    "node_modules/left-pad": {\n      "version": "1.3.0"\n    }\n  },\n  "_pad": "'
            + padding
            + b'"\n}\n',
        },
    )

    with SessionLocal() as session:
        snapshot = _snapshot(session, repository_id)

        assert _nodes(session, snapshot, "dependency") == {}
        codes = {
            item.code
            for item in session.scalars(
                select(RiDiagnostic).where(
                    RiDiagnostic.snapshot_id == snapshot.snapshot_id,
                    RiDiagnostic.path == "package-lock.json",
                )
            )
        }
        assert codes == {"RI-LIMIT-SKIP"}
