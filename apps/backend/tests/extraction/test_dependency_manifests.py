from app.extraction.manifests import DependencyManifestExtractor


EXTRACTOR = DependencyManifestExtractor()


def _extract(path: str, source: str):
    return EXTRACTOR.extract(path, source.encode("utf-8"))


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
