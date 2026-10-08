from starlette.formparsers import MultiPartParser

from conftest import register_user


def test_unauthenticated_upload_does_not_parse(client, monkeypatch):
    async def forbidden_parse(self):
        raise AssertionError("multipart parsed before authentication")

    monkeypatch.setattr(MultiPartParser, "parse", forbidden_parse)
    response = client.post("/repositories/upload", files={"file": ("sample.zip", b"bounded")})
    assert response.status_code == 401


def test_upload_body_cap_without_content_length(client):
    from app.core.config import get_settings

    auth = register_user(client, "upload@example.com")
    get_settings().max_upload_size_bytes = 16
    boundary = "test-boundary"

    def chunks():
        yield f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="repo.zip"\r\n\r\n'.encode()
        for _ in range(18):
            yield b"x" * 65536
        yield f"\r\n--{boundary}--\r\n".encode()

    response = client.post(
        "/repositories/upload",
        content=chunks(),
        headers={**auth["headers"], "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_declared_oversize_rejected_and_missing_file_validated(client):
    from app.core.config import get_settings

    auth = register_user(client, "upload@example.com")
    get_settings().max_upload_size_bytes = 16
    response = client.post(
        "/repositories/upload", content=b"x", headers={**auth["headers"], "Content-Length": "2000000"}
    )
    assert response.status_code == 413
    response = client.post("/repositories/upload", data={"field": "value"}, headers=auth["headers"])
    assert response.status_code == 422
