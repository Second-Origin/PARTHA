"""A GitHub URL as pasted from the browser is normalised, not rejected (#481)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import ValidationServiceError
from app.github.client import GitHubClient

from tests.api_assertions import assert_error_response


@pytest.fixture()
def client_under_test() -> GitHubClient:
    from app.core.config import Settings

    return GitHubClient(Settings(app_env="test"))


@pytest.mark.parametrize(
    ("pasted", "repo", "ref"),
    [
        ("https://github.com/octocat/Hello-World", "https://github.com/octocat/Hello-World", None),
        ("https://github.com/octocat/Hello-World/", "https://github.com/octocat/Hello-World", None),
        ("https://github.com/octocat/Hello-World.git", "https://github.com/octocat/Hello-World", None),
        ("https://github.com/octocat/Hello-World/tree/master", "https://github.com/octocat/Hello-World", "master"),
        ("https://github.com/octocat/Hello-World/tree/master/", "https://github.com/octocat/Hello-World", "master"),
        (
            "https://github.com/octocat/Hello-World/tree/feature/login-page",
            "https://github.com/octocat/Hello-World",
            "feature/login-page",
        ),
        ("https://github.com/octocat/Hello-World?tab=readme#top", "https://github.com/octocat/Hello-World", None),
        ("https://www.github.com/octocat/Hello-World/tree/v1.2", "https://github.com/octocat/Hello-World", "v1.2"),
    ],
)
def test_pasted_urls_split_into_repository_and_ref(client_under_test, pasted, repo, ref):
    assert client_under_test.split_import_url(pasted) == (repo, ref)


@pytest.mark.parametrize(
    "pasted",
    [
        "http://github.com/octocat/Hello-World",
        "https://gitlab.com/octocat/Hello-World",
        "https://github.com.evil.example/octocat/Hello-World",
        "https://github.com/octocat",
        "https://github.com/octocat/Hello-World/issues/4",
        "https://github.com/octocat/Hello-World/blob/main/README.md",
        "https://github.com/octocat/Hello-World/tree",
    ],
)
def test_other_urls_are_refused_with_what_to_paste(client_under_test, pasted):
    with pytest.raises(ValidationServiceError, match="https://github.com/owner/repo"):
        client_under_test.split_import_url(pasted)


def _stub_clone(monkeypatch: pytest.MonkeyPatch, seen: list[str | None]) -> None:
    def fake_clone(_: GitHubClient, __: str, destination: Path, branch: str | None = None) -> None:
        seen.append(branch)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "main.py").write_text("print('hi')\n", encoding="utf-8")

    monkeypatch.setattr(GitHubClient, "clone_public_repository", fake_clone)
    monkeypatch.setattr(GitHubClient, "read_head_commit", lambda *_: "c" * 40)
    monkeypatch.setattr(GitHubClient, "read_head_ref", lambda *_: "refs/heads/master")


def test_a_tree_url_imports_that_branch(auth_client, monkeypatch):
    seen: list[str | None] = []
    _stub_clone(monkeypatch, seen)

    response = auth_client.post(
        "/repositories/github", json={"url": "https://github.com/octocat/Hello-World/tree/master"}
    )

    assert response.status_code == 201, response.text
    assert seen == ["master"]
    assert response.json()["sourceUrl"] == "https://github.com/octocat/Hello-World"


def test_an_explicit_branch_wins_over_the_one_in_the_url(auth_client, monkeypatch):
    seen: list[str | None] = []
    _stub_clone(monkeypatch, seen)

    response = auth_client.post(
        "/repositories/github",
        json={"url": "https://github.com/octocat/Spoon-Knife/tree/master", "branch": "develop"},
    )

    assert response.status_code == 201, response.text
    assert seen == ["develop"]


def test_an_unsupported_page_url_is_a_clear_validation_error(auth_client):
    response = auth_client.post("/repositories/github", json={"url": "https://github.com/octocat/Hello-World/issues/1"})

    error = assert_error_response(response, 422, "validation_error")
    assert "https://github.com/owner/repo" in error.message
