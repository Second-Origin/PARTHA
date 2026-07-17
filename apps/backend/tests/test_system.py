import json
import logging

import pytest


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["environment"] == "development"


def test_readiness_endpoint(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "environment": "development",
        "checks": {"database": "ok", "storage": "ok"},
    }


def test_metrics_endpoint_exposes_request_counters(client):
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "partha_http_requests_total" in response.text
    assert 'partha_http_requests_by_route_total{method="GET",route="/health",status_code="200"}' in response.text


def test_request_id_header_is_returned(client):
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_readiness_endpoint_reports_database_failure(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "check_database_ready", lambda: False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "environment": "development",
        "checks": {"database": "error", "storage": "ok"},
    }


def test_readiness_endpoint_reports_storage_failure(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "check_storage_ready", lambda: False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "environment": "development",
        "checks": {"database": "ok", "storage": "error"},
    }


def test_openapi_schema_is_available(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/repositories/github" in paths
    assert "/analysis/{repository_id}/architecture" in paths
    assert "/ready" in paths


def test_http_errors_use_standard_shape(client):
    response = client.get("/missing-route")

    assert response.status_code == 404
    assert response.json() == {
        "code": "http_error",
        "message": "Not Found",
        "details": None,
        "request_id": response.headers["X-Request-ID"],
    }


def test_request_validation_errors_use_standard_shape(auth_client):
    # Authenticated so the request reaches body validation: /repositories is
    # auth-guarded at the router level, and an anonymous call would 401 first.
    response = auth_client.post("/repositories/github", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "request_validation_error"
    assert body["message"] == "Request validation failed."
    assert "errors" in body["details"]
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_unhandled_errors_use_standard_shape():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_server_error",
        "message": "An unexpected error occurred.",
        "details": None,
        "request_id": response.headers["X-Request-ID"],
    }
    body = response.text.lower()
    assert "boom" not in body
    assert "runtimeerror" not in body
    assert "traceback" not in body


def test_json_logging_includes_structured_fields(capsys):
    from app.core.logging import configure_logging

    configure_logging("INFO", "json")
    logging.getLogger("partha.test").info("Structured log test", extra={"component": "system"})

    output = capsys.readouterr().out.strip()
    payload = json.loads(output)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "partha.test"
    assert payload["message"] == "Structured log test"
    assert payload["extra"]["component"] == "system"


def test_json_logging_redacts_sensitive_extra_fields(capsys):
    from app.core.logging import configure_logging

    configure_logging("INFO", "json")
    logging.getLogger("partha.test").info("Sensitive log test", extra={"api_key": "secret-value"})

    output = capsys.readouterr().out.strip()
    payload = json.loads(output)

    assert payload["extra"]["api_key"] == "[REDACTED]"


def test_settings_rejects_invalid_log_level():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(log_level="VERBOSE")


def test_settings_rejects_invalid_log_format():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(log_format="pretty")


def test_settings_rejects_invalid_database_url():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(database_url="mysql://localhost/partha")


def test_settings_rejects_invalid_redis_url():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(redis_url="http://localhost:6379/0")


def test_settings_rejects_invalid_cors_origins():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(cors_origins=["localhost:5173"])


def test_settings_rejects_non_positive_limits():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(clone_timeout_seconds=0)
