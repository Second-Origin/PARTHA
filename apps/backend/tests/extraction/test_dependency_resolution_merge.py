"""Manifest declarations and lockfile resolutions on one identity (#209).

A dependency is one node. A manifest says what was asked for, a lockfile says
what was installed, and both must land on that node without either standing in
for the other and without a second stable-key record appearing.
"""

from __future__ import annotations

from app.extraction.base import ExtractedEvidence, ExtractedNode, ExtractionResult
from app.extraction.dependencies import DEPENDENCY_SET_ARRAY_KEYS, merge_dependency_facts
from app.extraction.lockfiles import LockfileExtractor
from app.extraction.manifests import DependencyManifestExtractor
from app.extraction.pipeline import ProducedExtraction

MANIFEST = (DependencyManifestExtractor.name, DependencyManifestExtractor.version)
LOCKFILE = (LockfileExtractor.name, LockfileExtractor.version)


def _declaration(stable_key: str, *, name: str, manifest_path: str, version: str, line: int = 1) -> ExtractedNode:
    return ExtractedNode(
        node_kind="dependency",
        stable_key=stable_key,
        name=name,
        language=None,
        evidence=(
            ExtractedEvidence(path=manifest_path, start_line=line, end_line=line, logical_line_count=max(line, 1)),
        ),
        properties={
            "ecosystem": stable_key.split(":")[1],
            "version": version,
            "dependency_type": "production",
            "manifest_path": manifest_path,
            "workspace_path": manifest_path.rsplit("/", 1)[0] if "/" in manifest_path else ".",
        },
    )


def _resolution(
    stable_key: str, *, name: str, lockfile_path: str, version: str, entry: str, line: int = 1
) -> ExtractedNode:
    return ExtractedNode(
        node_kind="dependency",
        stable_key=stable_key,
        name=name,
        language=None,
        evidence=(
            ExtractedEvidence(path=lockfile_path, start_line=line, end_line=line, logical_line_count=max(line, 1)),
        ),
        properties={
            "ecosystem": stable_key.split(":")[1],
            "resolved_version": version,
            "dependency_scope": "production",
            "lockfile_path": lockfile_path,
            "lockfile_format": "npm-package-lock",
            "lockfile_entry": entry,
            "workspace_path": lockfile_path.rsplit("/", 1)[0] if "/" in lockfile_path else ".",
        },
    )


def _produced(*nodes: ExtractedNode, producer: tuple[str, str]) -> ProducedExtraction:
    return ProducedExtraction(producer[0], producer[1], ExtractionResult(nodes=tuple(nodes)))


def _merged(produced):
    merged = merge_dependency_facts(produced)
    by_key: dict[str, ExtractedNode] = {}
    for item in merged:
        for node in item.result.nodes:
            if node.node_kind == "dependency":
                by_key.setdefault(node.stable_key, node)
    return merged, by_key


def test_a_declaration_and_a_resolution_share_one_node_without_replacing_each_other():
    produced = (
        _produced(
            _declaration("dep:npm:react", name="react", manifest_path="package.json", version="^18.3.0", line=4),
            producer=MANIFEST,
        ),
        _produced(
            _resolution(
                "dep:npm:react",
                name="react",
                lockfile_path="package-lock.json",
                version="18.3.1",
                entry="node_modules/react",
                line=9,
            ),
            producer=LOCKFILE,
        ),
    )

    _, by_key = _merged(produced)

    node = by_key["dep:npm:react"]
    assert [item["version"] for item in node.properties["declarations"]] == ["^18.3.0"]
    assert [item["resolved_version"] for item in node.properties["resolutions"]] == ["18.3.1"]
    # A caret range is not an installed version; neither collection is allowed
    # to stand in for the other.
    assert "resolved_version" not in node.properties["declarations"][0]
    assert "version" not in node.properties["resolutions"][0]


def test_a_dependency_with_no_lockfile_pin_reports_an_empty_resolution_list():
    """"Not resolved" and "never looked at" must not be indistinguishable."""

    produced = (
        _produced(
            _declaration("dep:pypi:requests", name="requests", manifest_path="pyproject.toml", version="==2.31.0"),
            producer=MANIFEST,
        ),
    )

    _, by_key = _merged(produced)

    assert by_key["dep:pypi:requests"].properties["resolutions"] == []
    assert len(by_key["dep:pypi:requests"].properties["declarations"]) == 1


def test_a_lockfile_only_dependency_reports_an_empty_declaration_list():
    produced = (
        _produced(
            _resolution(
                "dep:npm:tiny",
                name="tiny",
                lockfile_path="package-lock.json",
                version="0.1.0",
                entry="node_modules/a/node_modules/tiny",
            ),
            producer=LOCKFILE,
        ),
    )

    _, by_key = _merged(produced)

    # A lockfile entry proves an installed version, not a direct dependency.
    assert by_key["dep:npm:tiny"].properties["declarations"] == []
    assert len(by_key["dep:npm:tiny"].properties["resolutions"]) == 1


def test_two_installed_versions_of_one_package_are_two_resolutions_of_one_node():
    produced = (
        _produced(
            _resolution(
                "dep:npm:left-pad",
                name="left-pad",
                lockfile_path="package-lock.json",
                version="1.3.0",
                entry="node_modules/left-pad",
                line=8,
            ),
            _resolution(
                "dep:npm:left-pad",
                name="left-pad",
                lockfile_path="package-lock.json",
                version="1.2.0",
                entry="node_modules/util/node_modules/left-pad",
                line=15,
            ),
            producer=LOCKFILE,
        ),
    )

    merged, by_key = _merged(produced)

    assert len(by_key) == 1
    assert [item["resolved_version"] for item in by_key["dep:npm:left-pad"].properties["resolutions"]] == [
        "1.3.0",
        "1.2.0",
    ]
    emissions = [node for item in merged for node in item.result.nodes if node.node_kind == "dependency"]
    assert len(emissions) == 1


def test_each_producer_is_credited_only_with_the_evidence_it_read():
    produced = (
        _produced(
            _declaration("dep:npm:react", name="react", manifest_path="package.json", version="^18.3.0", line=4),
            producer=MANIFEST,
        ),
        _produced(
            _resolution(
                "dep:npm:react",
                name="react",
                lockfile_path="package-lock.json",
                version="18.3.1",
                entry="node_modules/react",
                line=9,
            ),
            producer=LOCKFILE,
        ),
    )

    merged = merge_dependency_facts(produced)

    evidence_by_producer = {
        (item.producer_name, item.producer_version): [
            (record.path, record.start_line)
            for node in item.result.nodes
            if node.node_kind == "dependency"
            for record in node.evidence
        ]
        for item in merged
        if any(node.node_kind == "dependency" for node in item.result.nodes)
    }
    assert evidence_by_producer[MANIFEST] == [("package.json", 4)]
    assert evidence_by_producer[LOCKFILE] == [("package-lock.json", 9)]
    # Every emission of the node must agree on its content, or ``add_node``
    # would reject the second write as a conflicting record.
    records = {
        (node.name, node.language, str(node.properties))
        for item in merged
        for node in item.result.nodes
        if node.node_kind == "dependency"
    }
    assert len(records) == 1


def test_a_declared_dependency_keeps_the_name_its_manifest_spelled():
    """The manifest spelling is what a reader of the repository recognizes."""

    produced = (
        _produced(
            _resolution(
                "dep:pypi:requests-toolbelt",
                name="Requests_Toolbelt",
                lockfile_path="poetry.lock",
                version="1.0.0",
                entry="Requests_Toolbelt",
            ),
            producer=LOCKFILE,
        ),
        _produced(
            _declaration(
                "dep:pypi:requests-toolbelt",
                name="requests-toolbelt",
                manifest_path="pyproject.toml",
                version=">=1.0",
            ),
            producer=MANIFEST,
        ),
    )

    _, by_key = _merged(produced)

    assert by_key["dep:pypi:requests-toolbelt"].name == "requests-toolbelt"


def test_merge_output_does_not_depend_on_the_order_files_were_read_in():
    manifest_a = _produced(
        _declaration("dep:npm:react", name="react", manifest_path="apps/admin/package.json", version="^18.3.0"),
        producer=MANIFEST,
    )
    manifest_b = _produced(
        _declaration("dep:npm:react", name="react", manifest_path="apps/web/package.json", version="^18.2.0"),
        producer=MANIFEST,
    )
    lock = _produced(
        _resolution(
            "dep:npm:react",
            name="react",
            lockfile_path="package-lock.json",
            version="18.3.1",
            entry="node_modules/react",
        ),
        producer=LOCKFILE,
    )

    forward = _merged((manifest_a, manifest_b, lock))[1]["dep:npm:react"]
    reverse = _merged((lock, manifest_b, manifest_a))[1]["dep:npm:react"]

    assert forward.properties == reverse.properties
    assert [item["manifest_path"] for item in forward.properties["declarations"]] == [
        "apps/admin/package.json",
        "apps/web/package.json",
    ]


def test_both_merged_collections_are_declared_set_arrays():
    """Canonical serialization must sort them, or the graph hash would drift."""

    assert DEPENDENCY_SET_ARRAY_KEYS == frozenset({"declarations", "resolutions"})


def test_an_unknown_producer_claiming_a_dependency_key_is_left_to_fail():
    """A real identity disagreement must not be papered over by the merge."""

    produced = (
        _produced(
            _declaration("dep:npm:react", name="react", manifest_path="package.json", version="^18.3.0"),
            producer=MANIFEST,
        ),
        _produced(
            _declaration("dep:npm:react", name="react", manifest_path="other.json", version="^18.3.0"),
            producer=("some-other-extractor", "9.9.9"),
        ),
    )

    assert merge_dependency_facts(produced) == produced
