"""Small assertions shared by HTTP integration tests."""

from httpx import Response

from app.core.exceptions import ErrorResponse


def assert_error_response(response: Response, status_code: int, code: str) -> ErrorResponse:
    """Assert the public error envelope, including request correlation."""
    assert response.status_code == status_code, response.text
    error = ErrorResponse.model_validate(response.json())
    assert error.code == code
    assert error.request_id == response.headers["X-Request-ID"]
    return error
