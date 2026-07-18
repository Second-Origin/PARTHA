import pytest
from httpx import Response

from tests.api_assertions import assert_error_response


def _error_response(payload: dict[str, object], request_id: str = "request-id") -> Response:
    return Response(status_code=422, json=payload, headers={"X-Request-ID": request_id})


def _valid_error_payload() -> dict[str, object]:
    return {
        "code": "validation_error",
        "message": "A validation error occurred.",
        "details": None,
        "request_id": "request-id",
    }


def test_assert_error_response_accepts_the_exact_public_envelope():
    error = assert_error_response(_error_response(_valid_error_payload()), 422, "validation_error")

    assert error.details is None


def test_assert_error_response_rejects_a_missing_envelope_field():
    payload = _valid_error_payload()
    del payload["details"]

    with pytest.raises(AssertionError, match="fields must be exactly"):
        assert_error_response(_error_response(payload), 422, "validation_error")


def test_assert_error_response_rejects_an_unexpected_envelope_field():
    payload = _valid_error_payload()
    payload["traceback"] = "sensitive stack trace"

    with pytest.raises(AssertionError, match="fields must be exactly"):
        assert_error_response(_error_response(payload), 422, "validation_error")


def test_assert_error_response_rejects_a_request_id_mismatch():
    with pytest.raises(AssertionError, match="request_id must match"):
        assert_error_response(_error_response(_valid_error_payload(), request_id="different-id"), 422, "validation_error")
