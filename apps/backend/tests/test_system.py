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
    assert response.json() == {"code": "http_error", "message": "Not Found", "details": None}


def test_request_validation_errors_use_standard_shape(client):
    response = client.post("/repositories/github", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "request_validation_error"
    assert body["message"] == "Request validation failed."
    assert "errors" in body["details"]


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
    }


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
