"""Reusable OpenAPI response metadata.

The API has one runtime error envelope, :class:`ErrorResponse`.  Route modules
use the helpers in this module to publish that fact consistently without
changing how requests are handled or how responses are serialised.
"""

from collections.abc import Mapping
from typing import Any

from app.core.exceptions import ErrorResponse


_ERROR_DESCRIPTIONS = {
    401: "Authentication is required or the access token is invalid.",
    404: "The requested resource does not exist or is not accessible to this user.",
    409: "The request conflicts with existing state.",
    422: "The request could not be validated.",
    429: "The request-rate limit has been exceeded.",
    500: "An unexpected server error occurred.",
    502: "An upstream service could not complete the request.",
    504: "An upstream service did not respond before the timeout.",
}

_ERROR_EXAMPLES: dict[int, dict[str, Any]] = {
    401: {
        "code": "unauthorized",
        "message": "Not authenticated.",
        "details": None,
        "request_id": "req_01HXYZEXAMPLE",
    },
    404: {
        "code": "not_found",
        "message": "Repository not found.",
        "details": {"repositoryId": "11111111-1111-1111-1111-111111111111"},
        "request_id": "req_01HXYZEXAMPLE",
    },
    409: {
        "code": "conflict_error",
        "message": "Repository has already been imported.",
        "details": {"repositoryId": "11111111-1111-1111-1111-111111111111"},
        "request_id": "req_01HXYZEXAMPLE",
    },
    422: {
        "code": "request_validation_error",
        "message": "Request validation failed.",
        "details": {"errors": [{"loc": ["body", "url"], "msg": "Field required"}]},
        "request_id": "req_01HXYZEXAMPLE",
    },
    429: {
        "code": "rate_limited",
        "message": "Too many requests. Try again shortly.",
        "details": {"retryAfterSeconds": 30},
        "request_id": "req_01HXYZEXAMPLE",
    },
    500: {
        "code": "internal_server_error",
        "message": "An unexpected error occurred.",
        "details": None,
        "request_id": "req_01HXYZEXAMPLE",
    },
    502: {
        "code": "external_service_error",
        "message": "AI provider request failed.",
        "details": {"provider": "openai"},
        "request_id": "req_01HXYZEXAMPLE",
    },
    504: {
        "code": "timeout_error",
        "message": "GitHub repository clone timed out.",
        "details": {"timeoutSeconds": 120},
        "request_id": "req_01HXYZEXAMPLE",
    },
}

_SUPPRESS_AUTOMATIC_422_MARKER = "x-partha-suppress-automatic-422"


def response_example(
    description: str,
    example: Any,
    *,
    media_type: str = "application/json",
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe a response body without affecting its runtime implementation."""
    media: dict[str, Any] = {"example": example}
    if schema is not None:
        media["schema"] = dict(schema)
    return {"description": description, "content": {media_type: media}}


def error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    """Return documented standard-error responses for the supplied statuses."""
    missing = set(status_codes) - _ERROR_DESCRIPTIONS.keys()
    if missing:
        raise ValueError(f"No OpenAPI error metadata for status codes: {sorted(missing)}")
    return {
        status_code: {
            "model": ErrorResponse,
            **response_example(
                _ERROR_DESCRIPTIONS[status_code],
                _ERROR_EXAMPLES[status_code],
                schema={"$ref": "#/components/schemas/ErrorResponse"},
            ),
        }
        for status_code in status_codes
    }


def suppress_automatic_validation_error() -> dict[str, bool]:
    """Mark an operation whose request shape cannot produce a 422 response.

    FastAPI adds a default 422 response for every route with any parameter,
    including unconstrained string path parameters. Routes using this marker are
    filtered from the generated document after FastAPI has assembled it.
    """
    return {_SUPPRESS_AUTOMATIC_422_MARKER: True}


def remove_suppressed_automatic_validation_errors(document: dict[str, Any]) -> None:
    """Remove FastAPI's synthetic 422 response from explicitly marked operations."""
    for path_item in document.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict) or not operation.pop(_SUPPRESS_AUTOMATIC_422_MARKER, False):
                continue
            operation.get("responses", {}).pop("422", None)


def documented_responses(
    success_status: int,
    success_description: str,
    success_example: Any,
    *error_status_codes: int,
    media_type: str = "application/json",
    schema: Mapping[str, Any] | None = None,
) -> dict[int, dict[str, Any]]:
    """Combine one success example with route-specific standard errors."""
    responses = {
        success_status: response_example(
            success_description,
            success_example,
            media_type=media_type,
            schema=schema,
        )
    }
    responses.update(error_responses(*error_status_codes))
    return responses
