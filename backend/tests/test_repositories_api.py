def test_list_repositories_starts_empty(client):
    response = client.get("/repositories")

    assert response.status_code == 200
    assert response.json() == {"data": [], "total": 0}


def test_github_import_rejects_non_github_url(client):
    response = client.post("/repositories/github", json={"url": "https://example.com/project"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
