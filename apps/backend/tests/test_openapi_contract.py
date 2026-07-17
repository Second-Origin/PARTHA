"""Regression coverage for the generated OpenAPI contract (#83).

The route table is intentionally enumerated here.  The equality check against
the generated document makes a new operation fail loudly until its public/auth
classification, response statuses, and examples are consciously documented.
"""

from collections.abc import Mapping


PUBLIC_OPERATIONS = {
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/metrics"),
}

EXPECTED_RESPONSES = {
    ("POST", "/auth/register"): {201, 409, 422, 429, 500},
    ("POST", "/auth/login"): {200, 401, 422, 429, 500},
    ("POST", "/auth/refresh"): {200, 401, 422, 429, 500},
    ("POST", "/auth/logout"): {204, 422, 429, 500},
    ("GET", "/auth/me"): {200, 401, 429, 500},
    ("POST", "/repositories/upload"): {201, 401, 409, 422, 429, 500},
    ("POST", "/repositories/github"): {201, 401, 409, 422, 429, 502, 504, 500},
    ("GET", "/repositories"): {200, 401, 429, 500},
    ("GET", "/repositories/{repository_id}"): {200, 401, 404, 422, 429, 500},
    ("GET", "/repositories/{repository_id}/file"): {200, 401, 404, 422, 429, 500},
    ("DELETE", "/repositories/{repository_id}"): {204, 401, 404, 422, 429, 500},
    ("POST", "/analysis/{repository_id}/start"): {200, 401, 404, 422, 429, 500},
    ("GET", "/analysis/{repository_id}/status"): {200, 401, 404, 422, 429, 500},
    ("GET", "/analysis/{repository_id}/architecture"): {200, 401, 404, 422, 429, 500},
    ("GET", "/analysis/{repository_id}/dependencies"): {200, 401, 404, 422, 429, 500},
    ("GET", "/analysis/{repository_id}/review"): {200, 401, 404, 422, 429, 500},
    ("GET", "/ai/config"): {200, 401, 429, 500},
    ("PUT", "/ai/config"): {200, 401, 422, 429, 500},
    ("POST", "/ai/test"): {200, 401, 422, 429, 502, 500},
    ("POST", "/ai/query"): {200, 401, 404, 422, 429, 502, 500},
    ("POST", "/ai/stream"): {200, 401, 404, 422, 429, 502, 500},
    ("POST", "/documentation/generate"): {200, 401, 404, 422, 429, 500},
    ("POST", "/export"): {200, 401, 404, 422, 429, 500},
    ("GET", "/health"): {200, 500},
    ("GET", "/ready"): {200, 503, 500},
    ("GET", "/metrics"): {200, 500},
}

BODY_MEDIA_TYPES = {
    ("POST", "/auth/register"): "application/json",
    ("POST", "/auth/login"): "application/json",
    ("POST", "/repositories/upload"): "multipart/form-data",
    ("POST", "/repositories/github"): "application/json",
    ("PUT", "/ai/config"): "application/json",
    ("POST", "/ai/test"): "application/json",
    ("POST", "/ai/query"): "application/json",
    ("POST", "/ai/stream"): "application/json",
    ("POST", "/documentation/generate"): "application/json",
    ("POST", "/export"): "application/json",
}

STANDARD_ERROR_STATUSES = {401, 404, 409, 422, 429, 500, 502, 504}


def _operations(document: Mapping[str, object]) -> dict[tuple[str, str], dict]:
    operations: dict[tuple[str, str], dict] = {}
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                operations[(method.upper(), path)] = operation
    return operations


def _response_media(operation: dict, status_code: int, media_type: str = "application/json") -> dict:
    return operation["responses"][str(status_code)]["content"][media_type]


def test_openapi_covers_every_live_api_operation(client):
    document = client.get("/openapi.json").json()

    assert set(_operations(document)) == set(EXPECTED_RESPONSES)


def test_openapi_declares_authentication_for_every_protected_operation(client):
    document = client.get("/openapi.json").json()
    operations = _operations(document)

    assert "HTTPBearer" in document["components"]["securitySchemes"]
    for key, operation in operations.items():
        if key in PUBLIC_OPERATIONS:
            assert not operation.get("security"), f"public operation unexpectedly requires auth: {key}"
        else:
            assert operation.get("security") == [{"HTTPBearer": []}], f"missing auth requirement: {key}"


def test_openapi_declares_exact_runtime_response_statuses(client):
    document = client.get("/openapi.json").json()

    for key, expected_statuses in EXPECTED_RESPONSES.items():
        actual_statuses = {int(status) for status in _operations(document)[key]["responses"]}
        assert actual_statuses == expected_statuses, f"response status drift for {key}"


def test_standard_error_responses_use_the_error_envelope_and_an_example(client):
    document = client.get("/openapi.json")
    components = document.json()["components"]["schemas"]
    assert "ErrorResponse" in components

    for key, operation in _operations(document.json()).items():
        for status_code in EXPECTED_RESPONSES[key] & STANDARD_ERROR_STATUSES:
            media = _response_media(operation, status_code)
            assert media["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}, (
                f"{key} {status_code} does not declare ErrorResponse"
            )
            assert media.get("example"), f"{key} {status_code} lacks an error example"


def test_openapi_has_request_examples_for_every_body_operation(client):
    operations = _operations(client.get("/openapi.json").json())

    for key, media_type in BODY_MEDIA_TYPES.items():
        request_body = operations[key]["requestBody"]["content"][media_type]
        assert request_body.get("schema"), f"{key} lacks a request-body schema"
        assert request_body.get("examples"), f"{key} lacks a request-body example"


def test_openapi_has_success_examples_except_for_no_content_deletes(client):
    operations = _operations(client.get("/openapi.json").json())

    for key, operation in operations.items():
        success_status = 201 if 201 in EXPECTED_RESPONSES[key] else 204 if 204 in EXPECTED_RESPONSES[key] else 200
        response = operation["responses"][str(success_status)]
        if success_status == 204:
            assert "content" not in response, f"{key} must not document a body for 204"
            continue

        media_type = "text/event-stream" if key == ("POST", "/ai/stream") else "text/plain" if key == ("GET", "/metrics") else "application/json"
        media = _response_media(operation, success_status, media_type)
        assert media.get("schema"), f"{key} lacks a success response schema"
        assert media.get("example") is not None, (
            f"{key} lacks a success response example"
        )


def test_readiness_documents_its_actual_non_error_503_payload(client):
    operation = _operations(client.get("/openapi.json").json())[("GET", "/ready")]
    media = _response_media(operation, 503)

    assert media["schema"]["type"] == "object"
    assert media["example"]["status"] == "not_ready"
