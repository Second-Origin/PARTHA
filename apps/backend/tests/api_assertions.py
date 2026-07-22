"""Small assertions shared by HTTP integration tests."""

from httpx import Response

from app.core.exceptions import ErrorResponse

ERROR_RESPONSE_FIELDS = frozenset({"code", "message", "details", "request_id"})


def assert_error_response(response: Response, status_code: int, code: str) -> ErrorResponse:
    """Assert the exact public error envelope, including request correlation."""
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert isinstance(payload, dict), f"error response must be a JSON object: {payload!r}"
    assert set(payload) == ERROR_RESPONSE_FIELDS, (
        "error response fields must be exactly "
        f"{sorted(ERROR_RESPONSE_FIELDS)}; got {sorted(payload)}"
    )

    error = ErrorResponse.model_validate(payload)
    assert error.code == code
    assert error.request_id == response.headers.get("X-Request-ID"), (
        "error response request_id must match the X-Request-ID header"
    )
    return error
