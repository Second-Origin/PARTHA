from tests.api_assertions import assert_error_response


def test_list_repositories_starts_empty(auth_client):
    response = auth_client.get("/repositories")

    assert response.status_code == 200
    assert response.json() == {"data": [], "total": 0}


def test_github_import_rejects_non_github_url(auth_client):
    response = auth_client.post("/repositories/github", json={"url": "https://example.com/project"})

    assert_error_response(response, 422, "validation_error")
