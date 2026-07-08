import base64
import io
import zipfile


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


def _import_sample(client):
    response = client.post(
        "/repositories/upload",
        files={
            "file": (
                "sample.zip",
                _zip_bytes(
                    {
                        "sample/package.json": b'{"name":"sample"}',
                        "sample/src/app.ts": b"export const answer = 42;\n",
                        "sample/assets/logo.png": PNG_BYTES,
                        "sample/data/blob.bin": b"\x00\x01\x02\x03binary\x00",
                    }
                ),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _get_file(client, repository_id: str, path: str):
    return client.get(f"/repositories/{repository_id}/file", params={"path": path})


def test_read_text_file_returns_real_content(client):
    repository_id = _import_sample(client)

    response = _get_file(client, repository_id, "/src/app.ts")

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "export const answer = 42;\n"
    assert body["isBinary"] is False
    assert body["isImage"] is False
    assert body["truncated"] is False
    assert body["size"] == len("export const answer = 42;\n")


def test_read_image_file_is_base64_encoded(client):
    repository_id = _import_sample(client)

    response = _get_file(client, repository_id, "/assets/logo.png")

    assert response.status_code == 200
    body = response.json()
    assert body["isImage"] is True
    assert body["isBinary"] is False
    assert body["mediaType"] == "image/png"
    assert base64.b64decode(body["content"]) == PNG_BYTES


def test_read_binary_file_is_flagged_without_content(client):
    repository_id = _import_sample(client)

    response = _get_file(client, repository_id, "/data/blob.bin")

    assert response.status_code == 200
    body = response.json()
    assert body["isBinary"] is True
    assert body["content"] == ""


def test_path_traversal_is_rejected(client):
    repository_id = _import_sample(client)

    response = _get_file(client, repository_id, "/../../secret.txt")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_missing_file_returns_not_found(client):
    repository_id = _import_sample(client)

    response = _get_file(client, repository_id, "/does-not-exist.ts")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_file_endpoint_requires_existing_repository(client):
    response = _get_file(client, "00000000-0000-0000-0000-000000000000", "/package.json")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
