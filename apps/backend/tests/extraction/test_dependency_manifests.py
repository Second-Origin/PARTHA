import pytest

from app.extraction.manifests import DependencyManifestExtractor


EXTRACTOR = DependencyManifestExtractor()


def _extract(path: str, source: str):
    return EXTRACTOR.extract(path, source.encode("utf-8"))


def _lines_by_key(result):
    return sorted((obs.subject_key, obs.evidence.start_line) for obs in result.observations)


def test_package_json_dependencies_are_observed_dependency_nodes():
    result = _extract(
        "package.json",
        '{"dependencies":{"react":"^18"},"devDependencies":{"vite":"^5"}}\n',
    )
    assert {node.stable_key for node in result.nodes} == {"dep:npm:react", "dep:npm:vite"}
    assert {(obs.subject_key, obs.referent_text) for obs in result.observations} == {
        ("dep:npm:react", "react"),
        ("dep:npm:vite", "vite"),
    }
    assert {obs.evidence.start_line for obs in result.observations} == {1}


def test_python_manifests_pep503_normalize_dependency_keys():
    pyproject = _extract(
        "pyproject.toml",
        '[project]\ndependencies = ["Fast_API>=1.0", "httpx[socks]>=0.1"]\n',
    )
    requirements = _extract("requirements.txt", "Fast_API>=1.0\nhttpx[socks]>=0.1\n")
    assert {node.stable_key for node in pyproject.nodes} == {"dep:pypi:fast-api", "dep:pypi:httpx"}
    assert {node.stable_key for node in requirements.nodes} == {"dep:pypi:fast-api", "dep:pypi:httpx"}


def test_malformed_manifest_is_a_visible_diagnostic():
    result = _extract("package.json", "{")
    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RI-SRC-MALFORMED"]


# --- Finding 4: exact declaration spans -------------------------------------


def test_npm_dependency_line_ignores_earlier_description_and_script_matches():
    # "react" appears in the package name, the description, and a script named
    # "react" — all before the real dependency declaration on line 6.
    source = """{
  "name": "react",
  "description": "built with react",
  "scripts": { "react": "react -w" },
  "dependencies": {
    "react": "^18"
  }
}
"""
    result = _extract("package.json", source)
    observations = [obs for obs in result.observations if obs.subject_key == "dep:npm:react"]
    assert len(observations) == 1
    assert observations[0].evidence.start_line == 6


def test_npm_dependency_in_multiple_sections_points_at_each_section_line():
    source = """{
  "dependencies": {
    "react": "^18"
  },
  "devDependencies": {
    "react": "^17"
  }
}
"""
    result = _extract("package.json", source)
    lines = sorted(obs.evidence.start_line for obs in result.observations if obs.subject_key == "dep:npm:react")
    assert lines == [3, 6]


def test_pyproject_multiline_dependency_array_points_at_each_element():
    # A project named "flask" and a description mentioning "django" precede the
    # array; brackets inside "httpx[socks]" must not shift element lines.
    source = """[project]
name = "flask"
description = "uses django"
dependencies = [
    "django>=4",
    "flask",
    "httpx[socks]>=0.1",
]
"""
    result = _extract("pyproject.toml", source)
    assert _lines_by_key(result) == [
        ("dep:pypi:django", 5),
        ("dep:pypi:flask", 6),
        ("dep:pypi:httpx", 7),
    ]


def test_requirements_declarations_stay_on_their_own_line():
    result = _extract("requirements.txt", "# comment\ndjango>=4\n-e .\nflask\n")
    assert _lines_by_key(result) == [("dep:pypi:django", 2), ("dep:pypi:flask", 4)]


def test_manifest_declarations_retain_exact_version_type_and_workspace_provenance():
    result = _extract(
        "apps/frontend/package.json",
        """{
  "devDependencies": {
    "vite": "^5"
  }
}
""",
    )

    node = result.nodes[0]
    assert node.properties == {
        "ecosystem": "npm",
        "version": "^5",
        "dependency_type": "development",
        "manifest_path": "apps/frontend/package.json",
        "workspace_path": "apps/frontend",
    }
    assert node.evidence[0].start_line == node.evidence[0].end_line == 3
    assert EXTRACTOR.producer == "dependency-manifest@1.2.0"


def test_requirements_url_fragments_are_retained_in_direct_reference_specifiers():
    result = _extract(
        "requirements.txt",
        "example @ https://host.example/archive.whl#sha256=first\n"
        "example @ https://host.example/archive.whl#sha256=second\n"
        "other>=1 # an ordinary comment\n",
    )

    declarations = [node.properties["version"] for node in result.nodes if node.name == "example"]
    assert declarations == [
        "@ https://host.example/archive.whl#sha256=first",
        "@ https://host.example/archive.whl#sha256=second",
    ]
    assert next(node for node in result.nodes if node.name == "other").properties["version"] == ">=1"


# --- Finding 5: fail closed on structurally invalid manifests ---------------


@pytest.mark.parametrize(
    "path,source",
    [
        ("package.json", "[]"),
        ("package.json", '"invalid"'),
        ("package.json", "42"),
        ("package.json", '{"dependencies": []}'),
        ("package.json", '{"dependencies": {"react": 18}}'),
        ("package.json", '{"peerDependencies": "react"}'),
        ("pyproject.toml", 'project = "invalid"'),
        ("pyproject.toml", "[project]\ndependencies = {}\n"),
        ("pyproject.toml", '[project]\ndependencies = "django"\n'),
        ("pyproject.toml", "[project]\ndependencies = [123]\n"),
    ],
)
def test_structurally_invalid_manifest_fails_closed(path, source):
    # No structurally invalid shape may escape as an AttributeError/TypeError or
    # degrade to a silent empty dependency list; each is a visible diagnostic
    # that names the normalized repository path.
    result = _extract(path, source)
    assert result.nodes == ()
    assert result.observations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RI-SRC-MALFORMED"]
    assert result.diagnostics[0].path == path
