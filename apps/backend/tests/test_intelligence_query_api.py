"""API coverage for the owner-scoped, stored-snapshot query boundary (#92)."""

from uuid import uuid4

import pytest

from app.intelligence.query_service import IMPACT_MAX_DEPTH
from tests.conftest import register_user


def _seed_snapshot(owner_id: str, *, suffix: str = "one", schema_version: str = "ri.v1") -> tuple[str, str]:
    """Persist a sealed graph while deliberately pointing at no real worktree."""

    from app.core.database import SessionLocal
    from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore, node_ref, observation_ref
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        repository_id = str(uuid4())
        revision_value = "sha256:" + ("a" if suffix == "one" else "b") * 64
        db.add(
            RepositoryRecord(
                id=repository_id,
                owner_id=owner_id,
                name=f"query-{suffix}",
                source="upload",
                revision_kind="upload",
                revision_value=revision_value,
                local_path=f"/definitely/inaccessible/{repository_id}",
                status="completed",
                file_tree=[],
            )
        )
        db.commit()
        store = SnapshotStore(db)
        snapshot = store.begin(
            repository_id=repository_id,
            revision=Revision("upload", revision_value),
            producer_version_set=["inventory@1.0.0", "resolver@1.0.0"],
            schema_version=schema_version,
        )

        def evidence(path: str, start: int, end: int, producer: str = "inventory") -> Evidence:
            return Evidence(path, start, end, producer, "1.0.0", logical_line_count=40)

        store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[evidence("README.md", 1, 2)])
        store.add_node(snapshot, node_kind="file", stable_key="file:src/app.py", name="app.py", language="python", evidence=[evidence("src/app.py", 1, 40)])
        store.add_node(snapshot, node_kind="symbol", stable_key=f"src/app.py::a_{suffix}", name=f"a_{suffix}", language="python", evidence=[evidence("src/app.py", 4, 6)])
        store.add_node(snapshot, node_kind="symbol", stable_key=f"src/app.py::z_{suffix}", name=f"z_{suffix}", language="python", evidence=[evidence("src/app.py", 10, 12)])
        observation = store.add_observation(
            snapshot,
            observed_kind="import",
            subject_kind="symbol",
            subject_key=f"src/app.py::a_{suffix}",
            referent_text="src/app.py::z_missing",
            evidence=evidence("src/app.py", 5, 5),
        )
        store.add_observation(
            snapshot,
            observed_kind="import",
            subject_kind="symbol",
            subject_key=f"src/app.py::z_{suffix}",
            referent_text="not.resolvable",
            evidence=evidence("src/app.py", 11, 11),
        )
        store.add_edge(
            snapshot,
            subject_kind="symbol",
            subject_key=f"src/app.py::a_{suffix}",
            predicate="imports",
            object_kind="file",
            object_key="file:src/app.py",
            producer="resolver",
            producer_version="1.0.0",
            evidence=[evidence("src/app.py", 5, 5, "resolver")],
            derived_from=[observation_ref(observation.observation_id)],
        )
        store.add_assertion(
            snapshot,
            subject_kind="symbol",
            subject_key=f"src/app.py::a_{suffix}",
            predicate="classified_as",
            value={"classification": "entrypoint"},
            producer="resolver",
            producer_version="1.0.0",
            derived_from=[node_ref(f"src/app.py::a_{suffix}")],
        )
        return repository_id, store.seal(snapshot).snapshot_id
    finally:
        db.close()


def _seed_impact_snapshot(owner_id: str) -> tuple[str, str]:
    """Persist an intentionally cyclic graph without a readable worktree."""

    from app.core.database import SessionLocal
    from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore, observation_ref
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        repository_id = str(uuid4())
        revision_value = "sha256:" + "c" * 64
        db.add(
            RepositoryRecord(
                id=repository_id,
                owner_id=owner_id,
                name="impact-query",
                source="upload",
                revision_kind="upload",
                revision_value=revision_value,
                local_path=f"/definitely/inaccessible/{repository_id}",
                status="completed",
                file_tree=[],
            )
        )
        db.commit()
        store = SnapshotStore(db)
        snapshot = store.begin(
            repository_id=repository_id,
            revision=Revision("upload", revision_value),
            producer_version_set=["inventory@1.0.0", "resolver@1.0.0"],
        )

        def evidence(path: str, line: int, producer: str = "inventory") -> Evidence:
            return Evidence(path, line, line, producer, "1.0.0", logical_line_count=40)

        store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[evidence("README.md", 1)])
        for index, path in enumerate(("a.py", "b.py", "c.py", "d.py"), start=2):
            store.add_node(
                snapshot,
                node_kind="file",
                stable_key=f"file:src/{path}",
                name=path,
                language="python",
                evidence=[evidence(f"src/{path}", index)],
            )
        store.add_node(
            snapshot,
            node_kind="dependency",
            stable_key="dep:pypi:requests",
            name="requests",
            evidence=[evidence("pyproject.toml", 6)],
        )

        def edge(
            subject_kind: str,
            subject_key: str,
            predicate: str,
            object_kind: str,
            object_key: str,
            line: int,
        ) -> None:
            path = "pyproject.toml" if predicate == "depends_on" else "src/relationships.py"
            observation = store.add_observation(
                snapshot,
                observed_kind="dependency" if predicate == "depends_on" else "import",
                subject_kind=subject_kind,
                subject_key=subject_key,
                referent_text=object_key,
                evidence=evidence(path, line),
            )
            store.add_edge(
                snapshot,
                subject_kind=subject_kind,
                subject_key=subject_key,
                predicate=predicate,
                object_kind=object_kind,
                object_key=object_key,
                producer="resolver",
                producer_version="1.0.0",
                evidence=[evidence(path, line, "resolver")],
                derived_from=[observation_ref(observation.observation_id)],
            )

        # A structural edge is deliberately present and must not enter the
        # impact result. The import edges form a cycle A -> B -> C -> A, with
        # a second direct relationship A -> D and a separate manifest edge.
        edge("repository", "repo:root", "contains", "file", "file:src/a.py", 7)
        edge("repository", "repo:root", "depends_on", "dependency", "dep:pypi:requests", 8)
        edge("file", "file:src/a.py", "imports", "file", "file:src/b.py", 9)
        edge("file", "file:src/b.py", "imports", "file", "file:src/c.py", 10)
        edge("file", "file:src/c.py", "imports", "file", "file:src/a.py", 11)
        edge("file", "file:src/a.py", "imports", "file", "file:src/d.py", 12)
        edge("file", "file:src/d.py", "imports", "file", "file:src/a.py", 13)
        return repository_id, store.seal(snapshot).snapshot_id
    finally:
        db.close()


def _seed_duplicate_heavy_impact_snapshot(owner_id: str) -> tuple[str, str]:
    """Persist a graph where duplicate paths would hide the overflow node."""

    from app.core.database import SessionLocal
    from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore, observation_ref
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        repository_id = str(uuid4())
        revision_value = "sha256:" + "d" * 64
        db.add(
            RepositoryRecord(
                id=repository_id,
                owner_id=owner_id,
                name="impact-duplicates",
                source="upload",
                revision_kind="upload",
                revision_value=revision_value,
                local_path=f"/definitely/inaccessible/{repository_id}",
                status="completed",
                file_tree=[],
            )
        )
        db.commit()
        store = SnapshotStore(db)
        snapshot = store.begin(
            repository_id=repository_id,
            revision=Revision("upload", revision_value),
            producer_version_set=["inventory@1.0.0", "resolver@1.0.0"],
        )

        def evidence(line: int, producer: str = "inventory") -> Evidence:
            return Evidence("src/graph.py", line, line, producer, "1.0.0", logical_line_count=300)

        store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[evidence(1)])
        for number in range(4):
            key = f"file:frontier/{number:02d}.py"
            store.add_node(snapshot, node_kind="file", stable_key=key, name=key.rsplit("/", 1)[-1], evidence=[evidence(number + 2)])
        for number in range(96):
            key = f"file:shared/{number:03d}.py"
            store.add_node(snapshot, node_kind="file", stable_key=key, name=key.rsplit("/", 1)[-1], evidence=[evidence(number + 6)])
        store.add_node(
            snapshot,
            node_kind="file",
            stable_key="file:overflow.py",
            name="overflow.py",
            evidence=[evidence(102)],
        )

        def edge(subject_key: str, object_key: str, line: int) -> None:
            observation = store.add_observation(
                snapshot,
                observed_kind="import",
                subject_kind="file" if subject_key != "repo:root" else "repository",
                subject_key=subject_key,
                referent_text=object_key,
                evidence=evidence(line),
                ordinal=line,
            )
            store.add_edge(
                snapshot,
                subject_kind="file" if subject_key != "repo:root" else "repository",
                subject_key=subject_key,
                predicate="imports",
                object_kind="file",
                object_key=object_key,
                producer="resolver",
                producer_version="1.0.0",
                evidence=[evidence(line, "resolver")],
                derived_from=[observation_ref(observation.observation_id)],
            )

        for number in range(4):
            edge("repo:root", f"file:frontier/{number:02d}.py", 103 + number)
        for number in range(96):
            edge(f"file:frontier/00.py", f"file:shared/{number:03d}.py", 107 + number)
        for number in range(13):
            edge(f"file:frontier/01.py", f"file:shared/{number:03d}.py", 203 + number)
        edge("file:frontier/03.py", "file:overflow.py", 216)
        return repository_id, store.seal(snapshot).snapshot_id
    finally:
        db.close()


def test_snapshot_query_endpoints_are_authenticated_owner_scoped_and_filesystem_independent(client, make_auth_headers):
    alice = make_auth_headers("alice-query@example.com")
    bob = make_auth_headers("bob-query@example.com")
    _, alice_snapshot = _seed_snapshot(alice["user"]["id"])
    _, bob_snapshot = _seed_snapshot(bob["user"]["id"], suffix="two")

    endpoints = ["", "/symbols", "/neighbours?nodeKey=repo:root", "/impact?nodeKey=repo:root", "/references", "/assertions", "/paths", "/evidence"]
    for endpoint in endpoints:
        unauthenticated = client.get(f"/intelligence/v1/snapshots/{alice_snapshot}{endpoint}")
        assert unauthenticated.status_code == 401

    metadata = client.get(f"/intelligence/v1/snapshots/{alice_snapshot}", headers=alice["headers"])
    assert metadata.status_code == 200
    assert metadata.json()["schemaVersion"] == "ri.v1"
    assert metadata.json()["state"] == "completed"
    assert metadata.json()["repositoryId"]
    assert metadata.json()["canonicalGraphHash"].startswith("sha256:")

    for endpoint in endpoints:
        denied = client.get(f"/intelligence/v1/snapshots/{alice_snapshot}{endpoint}", headers=bob["headers"])
        missing = client.get(f"/intelligence/v1/snapshots/snap_missing{endpoint}", headers=alice["headers"])
        assert denied.status_code == missing.status_code == 404
        assert denied.json()["code"] == missing.json()["code"] == "not_found"
        assert denied.json()["message"] == missing.json()["message"] == "Snapshot not found."

    # A second snapshot owned by Bob is not visible in Alice's collection queries.
    assert client.get(f"/intelligence/v1/snapshots/{bob_snapshot}/symbols", headers=alice["headers"]).status_code == 404


def test_snapshot_query_mappings_and_deterministic_pagination(client, make_auth_headers):
    owner = make_auth_headers("owner-query@example.com")
    _, snapshot_id = _seed_snapshot(owner["user"]["id"])
    base = f"/intelligence/v1/snapshots/{snapshot_id}"

    first = client.get(f"{base}/symbols?limit=1", headers=owner["headers"])
    second = client.get(f"{base}/symbols?limit=1&offset=1", headers=owner["headers"])
    assert first.status_code == second.status_code == 200
    assert first.json()["pagination"] == {"offset": 0, "limit": 1, "total": 2}
    assert second.json()["pagination"] == {"offset": 1, "limit": 1, "total": 2}
    assert first.json()["data"][0]["stableKey"] == "src/app.py::a_one"
    assert second.json()["data"][0]["stableKey"] == "src/app.py::z_one"
    assert first.json()["data"][0]["truthClass"] == "observed"
    assert first.json()["data"][0]["evidence"] == [{
        "schemaVersion": "ri.v1", "factKind": "node", "factId": "src/app.py::a_one", "path": "src/app.py",
        "startLine": 4, "endLine": 6, "granularity": "span", "extractor": "inventory", "extractorVersion": "1.0.0",
    }]

    neighbours = client.get(f"{base}/neighbours?nodeKey=src/app.py::a_one", headers=owner["headers"])
    assert neighbours.status_code == 200
    edge = neighbours.json()["data"][0]
    assert edge["predicate"] == "imports"
    assert edge["truthClass"] == "resolved"
    assert edge["derivedFrom"][0]["kind"] == "observation"
    assert edge["evidence"][0]["extractorVersion"] == "1.0.0"

    references = client.get(f"{base}/references", headers=owner["headers"])
    assert references.status_code == 200
    assert [item["edgeId"] for item in references.json()["data"]] == [edge["edgeId"]]
    # The unresolvable stored observation is not elevated to a relationship fact.
    assert "not.resolvable" not in references.text

    assertions = client.get(f"{base}/assertions", headers=owner["headers"])
    assert assertions.status_code == 200
    assert assertions.json()["data"][0]["truthClass"] == "inferred"
    assert assertions.json()["data"][0]["derivedFrom"] == [{"kind": "node", "identity": "src/app.py::a_one"}]

    paths = client.get(f"{base}/paths", headers=owner["headers"])
    assert paths.status_code == 200
    assert paths.json()["data"][0]["path"] == "src/app.py"
    assert paths.json()["data"][0]["node"]["evidence"][0]["path"] == "src/app.py"

    evidence = client.get(f"{base}/evidence", headers=owner["headers"])
    assert evidence.status_code == 200
    assert any(item["factKind"] == "edge" and item["extractor"] == "resolver" for item in evidence.json()["data"])


def test_query_rejects_owner_visible_unsupported_schema_without_cross_owner_disclosure(client, make_auth_headers):
    owner = make_auth_headers("owner-v2-query@example.com")
    other_owner = make_auth_headers("other-v2-query@example.com")
    _, snapshot_id = _seed_snapshot(owner["user"]["id"], schema_version="ri.v2")
    path = f"/intelligence/v1/snapshots/{snapshot_id}"

    for suffix in ["", "/symbols", "/neighbours?nodeKey=repo:root", "/impact?nodeKey=repo:root", "/references", "/assertions", "/paths", "/evidence"]:
        rejected = client.get(f"{path}{suffix}", headers=owner["headers"])
        assert rejected.status_code == 422
        assert rejected.json()["code"] == "unsupported_schema_version"
        assert rejected.json()["message"] == "Unsupported snapshot schema version: ri.v2."
        assert rejected.json()["details"] == {"received": "ri.v2", "supported": ["ri.v1"]}

    denied = client.get(path, headers=other_owner["headers"])
    missing = client.get("/intelligence/v1/snapshots/snap_missing", headers=other_owner["headers"])
    assert denied.status_code == missing.status_code == 404
    assert denied.json()["code"] == missing.json()["code"] == "not_found"
    assert denied.json()["message"] == missing.json()["message"] == "Snapshot not found."


@pytest.mark.parametrize("query", ["?limit=0", "?limit=101", "?offset=-1"])
def test_snapshot_query_rejects_invalid_pagination(client, make_auth_headers, query):
    owner = make_auth_headers(f"pagination-{uuid4().hex}@example.com")
    _, snapshot_id = _seed_snapshot(owner["user"]["id"])
    response = client.get(f"/intelligence/v1/snapshots/{snapshot_id}/symbols{query}", headers=owner["headers"])
    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_error"


def test_impact_query_returns_bounded_direct_and_transitive_relationships_with_provenance(client, make_auth_headers):
    owner = make_auth_headers("impact-owner@example.com")
    _, snapshot_id = _seed_impact_snapshot(owner["user"]["id"])
    base = f"/intelligence/v1/snapshots/{snapshot_id}/impact?nodeKey=file:src/a.py"

    depth_one = client.get(f"{base}&depth=1", headers=owner["headers"])
    depth_two = client.get(f"{base}&depth=2", headers=owner["headers"])
    repeated = client.get(f"{base}&depth=2", headers=owner["headers"])

    assert depth_one.status_code == depth_two.status_code == repeated.status_code == 200
    assert depth_two.json() == repeated.json()
    assert depth_two.json()["schemaVersion"] == "ri.v1"
    assert depth_one.json()["depth"] == 1
    assert [item["nodeKey"] for item in depth_one.json()["dependencies"]["data"]] == [
        "file:src/b.py",
        "file:src/d.py",
    ]
    assert [item["nodeKey"] for item in depth_two.json()["dependencies"]["data"]] == [
        "file:src/b.py",
        "file:src/d.py",
        "file:src/c.py",
    ]
    assert [item["depth"] for item in depth_two.json()["dependencies"]["data"]] == [1, 1, 2]
    assert [item["nodeKey"] for item in depth_two.json()["dependents"]["data"]] == [
        "file:src/c.py",
        "file:src/d.py",
        "file:src/b.py",
    ]
    assert [item["depth"] for item in depth_two.json()["dependents"]["data"]] == [1, 1, 2]
    assert "file:src/a.py" not in {
        item["nodeKey"]
        for direction in ("dependencies", "dependents")
        for item in depth_two.json()[direction]["data"]
    }
    first_hop = depth_two.json()["dependencies"]["data"][0]
    assert first_hop["via"]["predicate"] == "imports"
    assert first_hop["via"]["evidence"][0]["extractor"] == "resolver"
    assert first_hop["via"]["derivedFrom"][0]["kind"] == "observation"
    assert depth_two.json()["dependencies"]["limitReached"] is False
    assert depth_two.json()["dependents"]["limitReached"] is False

    repository = client.get(
        f"/intelligence/v1/snapshots/{snapshot_id}/impact?nodeKey=repo:root",
        headers=owner["headers"],
    )
    assert repository.status_code == 200
    assert [item["nodeKey"] for item in repository.json()["dependencies"]["data"]] == ["dep:pypi:requests"]


def test_impact_query_enforces_depth_and_result_bounds(client, make_auth_headers, monkeypatch):
    owner = make_auth_headers("impact-bounds@example.com")
    _, snapshot_id = _seed_impact_snapshot(owner["user"]["id"])
    path = f"/intelligence/v1/snapshots/{snapshot_id}/impact?nodeKey=file:src/a.py"

    at_cap = client.get(f"{path}&depth={IMPACT_MAX_DEPTH}", headers=owner["headers"])
    too_deep = client.get(f"{path}&depth={IMPACT_MAX_DEPTH + 1}", headers=owner["headers"])
    zero_depth = client.get(f"{path}&depth=0", headers=owner["headers"])

    assert at_cap.status_code == 200
    assert [item["nodeKey"] for item in at_cap.json()["dependencies"]["data"]] == [
        "file:src/b.py",
        "file:src/d.py",
        "file:src/c.py",
    ]
    assert len(at_cap.json()["dependencies"]["data"]) == len(
        {item["nodeKey"] for item in at_cap.json()["dependencies"]["data"]}
    )
    assert too_deep.status_code == zero_depth.status_code == 422
    assert too_deep.json()["code"] == zero_depth.json()["code"] == "request_validation_error"

    monkeypatch.setattr("app.intelligence.query_service.IMPACT_MAX_RESULTS_PER_DIRECTION", 1)
    capped = client.get(f"{path}&depth=1", headers=owner["headers"])
    assert capped.status_code == 200
    assert [item["nodeKey"] for item in capped.json()["dependencies"]["data"]] == ["file:src/b.py"]
    assert capped.json()["dependencies"]["limitReached"] is True


def test_impact_query_detects_cap_after_duplicate_paths_and_uses_canonical_hop(client, make_auth_headers):
    """The cap applies after SQL deduplication, not to raw duplicate edges."""

    owner = make_auth_headers("impact-duplicate-paths@example.com")
    _, snapshot_id = _seed_duplicate_heavy_impact_snapshot(owner["user"]["id"])
    path = f"/intelligence/v1/snapshots/{snapshot_id}/impact?nodeKey=repo:root&depth=2"

    response = client.get(path, headers=owner["headers"])
    repeated = client.get(path, headers=owner["headers"])

    assert response.status_code == repeated.status_code == 200
    assert response.json() == repeated.json()
    dependencies = response.json()["dependencies"]
    assert dependencies["limitReached"] is True
    assert len(dependencies["data"]) == 100
    assert [item["nodeKey"] for item in dependencies["data"]] == [
        *(f"file:frontier/{number:02d}.py" for number in range(4)),
        *(f"file:shared/{number:03d}.py" for number in range(96)),
    ]
    assert "file:overflow.py" not in {item["nodeKey"] for item in dependencies["data"]}
    assert dependencies["data"][4]["via"]["subjectKey"] == "file:frontier/00.py"
    assert dependencies["data"][4]["via"]["predicate"] == "imports"


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "?nodeKey=",
        "?nodeKey=file:src/a.py&depth=0",
        f"?nodeKey=file:src/a.py&depth={IMPACT_MAX_DEPTH + 1}",
    ],
)
def test_impact_query_rejects_malformed_parameters(client, make_auth_headers, suffix):
    owner = make_auth_headers(f"impact-invalid-{uuid4().hex}@example.com")
    _, snapshot_id = _seed_impact_snapshot(owner["user"]["id"])
    response = client.get(f"/intelligence/v1/snapshots/{snapshot_id}/impact{suffix}", headers=owner["headers"])

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_error"


def test_impact_query_hides_unknown_nodes_and_cross_owner_snapshots(client, make_auth_headers):
    owner = make_auth_headers("impact-visible@example.com")
    other_owner = make_auth_headers("impact-hidden@example.com")
    _, snapshot_id = _seed_impact_snapshot(owner["user"]["id"])
    path = f"/intelligence/v1/snapshots/{snapshot_id}/impact?nodeKey=file:src/missing.py"

    unknown_node = client.get(path, headers=owner["headers"])
    denied = client.get(path, headers=other_owner["headers"])
    missing = client.get(
        "/intelligence/v1/snapshots/snap_missing/impact?nodeKey=file:src/missing.py",
        headers=other_owner["headers"],
    )

    assert unknown_node.status_code == 404
    assert unknown_node.json()["code"] == "not_found"
    assert unknown_node.json()["message"] == "Node not found in snapshot."
    assert denied.status_code == missing.status_code == 404
    assert denied.json()["code"] == missing.json()["code"] == "not_found"
    assert denied.json()["message"] == missing.json()["message"] == "Snapshot not found."


def test_snapshot_query_openapi_documents_versioned_routes_and_schemas(client):
    document = client.get("/openapi.json").json()
    assert "/intelligence/v1/snapshots/{snapshot_id}/symbols" in document["paths"]
    assert "/intelligence/v1/snapshots/{snapshot_id}/impact" in document["paths"]
    assert "RiImpactResponse" in document["components"]["schemas"]
    assert "RiSymbolsResponse" in document["components"]["schemas"]
    assert "RiEvidenceResponse" in document["components"]["schemas"]
    assert document["components"]["schemas"]["RiSymbolsResponse"]["properties"]["schemaVersion"]["const"] == "ri.v1"
