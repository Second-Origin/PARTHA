import pytest

from app.intelligence import canonical


def test_rfc_identity_and_config_vectors_are_reproduced_exactly():
    config = {
        "max_file_bytes": 524288,
        "extractors": ["typescript-ast", "python-ast", "repository-inventory"],
        "resolvers": ["route-resolver", "import-resolver", "reference-resolver"],
        "classifiers": ["architecture-classifier"],
    }
    assert canonical.compute_config_hash({}) == (
        "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    )
    assert canonical.compute_config_hash(
        config,
        set_array_keys=frozenset({"extractors", "resolvers", "classifiers"}),
    ) == "sha256:48e96ba328a03db38556f22d2831d171b82e1ce9287c575328de4bc249da1abe"

    edge_id = canonical.compute_edge_id(
        "src/auth/service.ts::AuthService.login",
        "calls",
        "src/auth/tokens.ts::issueToken",
    )
    assert edge_id == "edge:sha256:90594a4734e993838e2db11f9d3bb5ede0cab2f1c70730ca8c4ab407c93bd69e"

    evidence = {
        "path": "src/auth/service.ts",
        "start_line": 41,
        "end_line": 41,
        "extractor": "typescript-ast",
        "extractor_version": "1.0.0",
    }
    observation_id = canonical.compute_observation_id(
        revision_kind="git",
        revision_value="9f1d0c7a2b6e4c5d8f3a1b0c7d9e2f4a6b8c0d1e",
        observed_kind="call",
        subject_kind="symbol",
        subject_key="src/auth/service.ts::AuthService.login",
        referent_text="issueToken",
        ordinal=1,
        evidence=evidence,
    )
    assert observation_id == "obs:sha256:ad475fae87c8121b76673172a560885335661f68ea90e4b5fa661be9b884f24a"

    assertion_id = canonical.compute_assertion_id(
        subject_kind="module",
        subject_key="mod:app/services",
        predicate="classified_as",
        value={"classification": "business-logic-layer", "confidence": "heuristic"},
        truth_class="inferred",
        producer="architecture-classifier",
        producer_version="1.0.0",
        derived_from=[
            {
                "kind": "edge",
                "edge_id": "edge:sha256:e20b7e1135e0535ffb7c19cb2066a0645d9e980d2071816ddfc967431b774807",
            },
            {"kind": "node", "stable_key": "mod:app/services"},
        ],
    )
    assert assertion_id == (
        "assertion:sha256:c081743f9923c3f5036ebda30de9be443deb58002b6bfa1102f388e64a024d57"
    )


def test_config_arrays_preserve_order_unless_explicitly_declared_as_sets():
    first = canonical.compute_config_hash({"pipeline": ["parse", "resolve"]})
    reversed_order = canonical.compute_config_hash({"pipeline": ["resolve", "parse"]})
    assert first != reversed_order

    set_first = canonical.compute_config_hash(
        {"extractors": ["python", "typescript", "python"]},
        set_array_keys=frozenset({"extractors"}),
    )
    set_second = canonical.compute_config_hash(
        {"extractors": ["typescript", "python"]},
        set_array_keys=frozenset({"extractors"}),
    )
    assert set_first == set_second
    assert canonical.compute_config_hash(
        {"include_path": r"src\.\features"},
        path_keys=frozenset({"include_path"}),
    ) == canonical.compute_config_hash(
        {"include_path": "src/features"},
        path_keys=frozenset({"include_path"}),
    )


def test_paths_unicode_and_unsupported_numbers_are_normalized_or_rejected():
    assert canonical.normalize_repo_path(r"src\.\auth\..\main.py") == "src/main.py"
    assert canonical.normalize_stable_key("file", "file:src/./main.py") == "file:src/main.py"
    assert canonical.canonical_json_bytes({"name": "e\u0301"}) == canonical.canonical_json_bytes(
        {"name": "\u00e9"}
    )
    with pytest.raises(canonical.PathEscapeError):
        canonical.normalize_repo_path("../../etc/passwd")
    with pytest.raises(canonical.PathEscapeError):
        canonical.normalize_repo_path("/etc/passwd")
    with pytest.raises(canonical.CanonicalizationError):
        canonical.canonical_json_bytes({"confidence": 0.9})
    with pytest.raises(canonical.CanonicalizationError):
        canonical.canonical_json_bytes({"e\u0301": 1, "\u00e9": 2})
    with pytest.raises(canonical.CanonicalizationError):
        canonical.canonical_json_bytes({"too_large": 2**53})


def test_jcs_object_keys_use_utf16_code_unit_order():
    # U+1F600 sorts before U+E000 under JCS UTF-16 ordering (D83D < E000),
    # although Python code-point ordering would place U+E000 first.
    assert canonical.canonical_json_bytes({"\ue000": 1, "\U0001f600": 2}) == (
        '{"\U0001f600":2,"\ue000":1}'.encode()
    )


def test_canonical_graph_hash_is_independent_of_insertion_order_and_volatile_fields():
    evidence_a = {
        "path": "src/a.py",
        "start_line": 1,
        "end_line": 2,
        "extractor": "python-ast",
        "extractor_version": "1.0.0",
    }
    evidence_b = {**evidence_a, "start_line": 5, "end_line": 5}
    nodes = [
        {
            "node_kind": "repository",
            "stable_key": "repo:root",
            "truth_class": "observed",
            "evidence": [evidence_a],
        },
        {
            "node_kind": "file",
            "stable_key": "file:src/a.py",
            "truth_class": "observed",
            "evidence": [evidence_b, evidence_a],
        },
    ]
    edge_id = canonical.compute_edge_id("repo:root", "contains", "file:src/a.py")
    edges = [
        {
            "edge_id": edge_id,
            "subject_kind": "repository",
            "subject_key": "repo:root",
            "predicate": "contains",
            "object_kind": "file",
            "object_key": "file:src/a.py",
            "truth_class": "resolved",
            "producer": "inventory-resolver",
            "producer_version": "1.0.0",
            "evidence": [evidence_b, evidence_a],
            "derived_from": [{"kind": "node", "stable_key": "file:src/a.py"}],
            "database_id": 99,
            "created_at": "volatile and ignored by the record builder",
        }
    ]
    arguments = {
        "revision_kind": "git",
        "revision_value": "0123456789abcdef0123456789abcdef01234567",
        "producer_version_set": ["inventory-resolver@1.0.0", "python-ast@1.0.0"],
        "config_hash": canonical.compute_config_hash({}),
        "assertions": [],
        "observations": [],
        "diagnostics": [],
    }
    first = canonical.compute_canonical_graph_hash(nodes=nodes, edges=edges, **arguments)
    second = canonical.compute_canonical_graph_hash(
        nodes=list(reversed(nodes)),
        edges=[{**edges[0], "evidence": list(reversed(edges[0]["evidence"]))}],
        **arguments,
    )
    assert first == second
    assert first.startswith("sha256:") and len(first) == 71
