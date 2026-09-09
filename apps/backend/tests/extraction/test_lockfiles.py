"""Resolved-version extraction from supported lockfiles (#209).

A lockfile fact is only useful if it is *exact*: the right pin, attributed to
the right logical dependency, at the right line. These tests pin all three, and
pin equally hard the cases where nothing may be claimed at all.
"""

from __future__ import annotations

import pytest

from app.extraction.base import (
    RI_EXT_UNSUPPORTED,
    RI_SEC_PATH_ESCAPE,
    RI_SRC_BINARY,
    RI_SRC_MALFORMED,
)
from app.extraction.lockfiles import (
    SUPPORTED_NPM_LOCKFILE_VERSIONS,
    SUPPORTED_POETRY_LOCK_MAJORS,
    LockfileExtractor,
)
from app.extraction.support_matrix import supported_lockfile_filenames

NPM_LOCK = b"""{
  "name": "web",
  "lockfileVersion": 3,
  "packages": {
    "": {
      "name": "web"
    },
    "node_modules/@scope/pkg": {
      "version": "2.0.1",
      "dev": true
    },
    "node_modules/left-pad": {
      "version": "1.3.0"
    },
    "node_modules/maybe": {
      "version": "0.4.0",
      "optional": true
    },
    "node_modules/util/node_modules/left-pad": {
      "version": "1.2.0"
    },
    "node_modules/workspace-link": {
      "resolved": "packages/app",
      "link": true
    },
    "packages/app": {
      "name": "@web/app",
      "version": "1.0.0"
    }
  }
}
"""

POETRY_LOCK = b"""[[package]]
name = "Requests_Toolbelt"
version = "1.0.0"
optional = false

[[package]]
name = "pytest"
version = "8.3.4"
category = "dev"
description = \"\"\"
A description that mentions [[package]] on purpose.
\"\"\"

[metadata]
lock-version = "2.0"
"""


def _nodes(result):
    """Index by stable key, keeping the first emission.

    One key can legitimately be emitted twice — a nested npm tree resolves the
    same dependency to a second version — so this must not silently keep the
    last one. Tests about multiple resolutions read ``result.nodes`` directly.
    """

    indexed: dict[str, object] = {}
    for node in result.nodes:
        indexed.setdefault(node.stable_key, node)
    return indexed


def _extract(path: str, source: bytes):
    return LockfileExtractor().extract(path, source)


# --- supports() -------------------------------------------------------------


def test_supported_filenames_come_from_the_capability_registry():
    extractor = LockfileExtractor()

    assert set(supported_lockfile_filenames()) == {"package-lock.json", "poetry.lock"}
    assert extractor.supports("package-lock.json")
    assert extractor.supports("apps/web/poetry.lock")
    # Formats the registry declares out of scope are never opened at all, so
    # they can never produce a half-understood resolution.
    assert not extractor.supports("yarn.lock")
    assert not extractor.supports("pnpm-lock.yaml")
    assert not extractor.supports("Pipfile.lock")
    assert not extractor.supports("uv.lock")


# --- npm --------------------------------------------------------------------


def test_npm_lockfile_pins_exact_versions_at_their_own_declaration_lines():
    result = _extract("package-lock.json", NPM_LOCK)
    nodes = _nodes(result)

    assert nodes["dep:npm:@scope/pkg"].properties["resolved_version"] == "2.0.1"
    assert nodes["dep:npm:left-pad"].properties["resolved_version"] == "1.3.0"
    # The line is the entry's own key inside ``packages``, not a substring hit.
    assert nodes["dep:npm:@scope/pkg"].evidence[0].start_line == 8
    assert nodes["dep:npm:left-pad"].evidence[0].start_line == 12
    for node in result.nodes:
        evidence = node.evidence[0]
        assert evidence.start_line == evidence.end_line
        assert evidence.path == "package-lock.json"


def test_npm_tree_flags_map_onto_the_manifest_dependency_vocabulary():
    nodes = _nodes(_extract("package-lock.json", NPM_LOCK))

    assert nodes["dep:npm:left-pad"].properties["dependency_scope"] == "production"
    assert nodes["dep:npm:@scope/pkg"].properties["dependency_scope"] == "development"
    assert nodes["dep:npm:maybe"].properties["dependency_scope"] == "optional"


def test_a_nested_tree_entry_is_a_second_resolution_of_one_dependency():
    """``node_modules/util/node_modules/left-pad`` is left-pad, not a new package."""

    result = _extract("package-lock.json", NPM_LOCK)
    left_pad = [node for node in result.nodes if node.stable_key == "dep:npm:left-pad"]

    assert len(left_pad) == 2
    assert {node.properties["resolved_version"] for node in left_pad} == {"1.3.0", "1.2.0"}
    assert {node.properties["lockfile_entry"] for node in left_pad} == {
        "node_modules/left-pad",
        "node_modules/util/node_modules/left-pad",
    }


def test_workspace_and_root_entries_are_not_resolved_registry_versions():
    nodes = _nodes(_extract("package-lock.json", NPM_LOCK))

    # ``"link": true`` is a symlink into the repository, and ``packages/app`` is
    # the workspace directory itself — neither is an installed registry version.
    assert "dep:npm:workspace-link" not in nodes
    assert "dep:npm:@web/app" not in nodes
    assert "dep:npm:web" not in nodes


def test_an_entry_without_a_concrete_version_claims_nothing():
    result = _extract(
        "package-lock.json",
        b'{"lockfileVersion": 3, "packages": {"node_modules/ghost": {"resolved": "https://x/y"}}}',
    )

    assert result.nodes == ()
    assert result.observations == ()


@pytest.mark.parametrize("lockfile_version", [1, 4, 0])
def test_an_unsupported_npm_lockfile_version_is_disclosed_not_parsed(lockfile_version):
    source = b'{"lockfileVersion": %d, "dependencies": {"left-pad": {"version": "1.3.0"}}}' % lockfile_version

    result = _extract("package-lock.json", source)

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_EXT_UNSUPPORTED]
    # Well-formed JSON in an unsupported revision is not malformed source, and
    # saying so would be a false claim about the file.
    assert str(list(SUPPORTED_NPM_LOCKFILE_VERSIONS)) in result.diagnostics[0].message
    assert result.diagnostics[0].subject == "file:package-lock.json"


# --- poetry -----------------------------------------------------------------


def test_poetry_lockfile_pins_versions_and_folds_names_per_pep_503():
    result = _extract("poetry.lock", POETRY_LOCK)
    nodes = _nodes(result)

    # ``Requests_Toolbelt`` and a manifest's ``requests-toolbelt`` are one entity.
    assert nodes["dep:pypi:requests-toolbelt"].properties["resolved_version"] == "1.0.0"
    assert nodes["dep:pypi:requests-toolbelt"].name == "Requests_Toolbelt"
    assert nodes["dep:pypi:pytest"].properties["resolved_version"] == "8.3.4"


def test_poetry_headers_are_located_through_strings_not_by_line_matching():
    """A ``[[package]]`` inside a description must not shift every later line."""

    nodes = _nodes(_extract("poetry.lock", POETRY_LOCK))

    assert nodes["dep:pypi:requests-toolbelt"].evidence[0].start_line == 1
    assert nodes["dep:pypi:pytest"].evidence[0].start_line == 6


def test_poetry_reports_an_unknown_group_rather_than_guessing_production():
    nodes = _nodes(_extract("poetry.lock", POETRY_LOCK))

    # lock-version 2 dropped ``category``; this entry genuinely does not say.
    assert nodes["dep:pypi:requests-toolbelt"].properties["dependency_scope"] is None
    assert nodes["dep:pypi:pytest"].properties["dependency_scope"] == "development"


def test_an_unsupported_poetry_lock_version_is_disclosed_not_parsed():
    source = b'[[package]]\nname = "a"\nversion = "1.0"\n\n[metadata]\nlock-version = "9.0"\n'

    result = _extract("poetry.lock", source)

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_EXT_UNSUPPORTED]
    assert str(list(SUPPORTED_POETRY_LOCK_MAJORS)) in result.diagnostics[0].message


# --- observations -----------------------------------------------------------


def test_each_resolution_emits_an_observation_carrying_the_pinned_version():
    result = _extract("poetry.lock", POETRY_LOCK)

    observations = [
        (observation.observed_kind, observation.subject_key, observation.referent_text, observation.ordinal)
        for observation in result.observations
    ]
    assert observations == [
        ("resolution", "dep:pypi:requests-toolbelt", "1.0.0", 1),
        ("resolution", "dep:pypi:pytest", "8.3.4", 1),
    ]
    for observation in result.observations:
        assert observation.subject_kind == "dependency"


# --- failure paths ----------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("package-lock.json", b"{not json"),
        ("package-lock.json", b'{"lockfileVersion": 3}'),
        ("package-lock.json", b'{"lockfileVersion": 3, "packages": []}'),
        ("package-lock.json", b'{"lockfileVersion": "3", "packages": {}}'),
        ("package-lock.json", b'[{"lockfileVersion": 3}]'),
        ("package-lock.json", b'{"lockfileVersion": 3, "packages": {"node_modules/a": "1.0.0"}}'),
        ("poetry.lock", b"[[package\n"),
        ("poetry.lock", b'[[package]]\nname = "a"\n\n[metadata]\nlock-version = "2.0"\n'),
        ("poetry.lock", b'[[package]]\nname = "a"\nversion = "1"\n'),
        ("poetry.lock", b"[metadata]\nlock-version = 2\n"),
    ],
)
def test_structurally_invalid_lockfiles_fail_closed_with_one_diagnostic(path, source):
    result = _extract(path, source)

    assert result.nodes == ()
    assert result.observations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SRC_MALFORMED]


def test_an_empty_but_valid_lockfile_claims_nothing_without_complaining():
    result = _extract("poetry.lock", b'[metadata]\nlock-version = "2.0"\n')

    assert result.nodes == ()
    assert result.diagnostics == ()


def test_a_binary_lockfile_is_excluded_from_line_addressed_extraction():
    result = _extract("package-lock.json", b'{"lockfileVersion": 3,\x00}')

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SRC_BINARY]


def test_undecodable_bytes_are_reported_as_malformed_source():
    result = _extract("package-lock.json", b"\xff\xfe{")

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SRC_MALFORMED]


def test_a_path_escaping_the_repository_root_is_rejected_before_extraction():
    result = _extract("../../package-lock.json", NPM_LOCK)

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SEC_PATH_ESCAPE]


# --- determinism ------------------------------------------------------------


def test_repeated_extraction_of_one_lockfile_is_byte_identical():
    first = _extract("apps/web/package-lock.json", NPM_LOCK)
    second = _extract("apps/web/package-lock.json", NPM_LOCK)

    assert first == second
    assert {node.properties["workspace_path"] for node in first.nodes} == {"apps/web"}
