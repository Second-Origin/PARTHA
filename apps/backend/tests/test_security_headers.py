ALLOWED_ORIGIN = "http://testserver"  # matches CORS_ORIGINS set by the client fixture


def test_security_headers_present_on_responses(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "max-age=" in response.headers["Strict-Transport-Security"]
    assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")


def test_csp_skipped_on_interactive_docs(client):
    # The strict default-src 'none' policy would blank Swagger UI, so it must not
    # be applied to the docs routes (the other headers still are).
    response = client.get("/docs")

    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_cors_allows_configured_origin(client):
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_rejects_unlisted_origin(client):
    response = client.get("/health", headers={"Origin": "http://evil.example"})

    assert response.status_code == 200  # the request still runs...
    # ...but the browser is told it may not read the response.
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_reports_allowed_methods_not_wildcard(client):
    response = client.options(
        "/repositories",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    allow_methods = response.headers["access-control-allow-methods"]
    assert "POST" in allow_methods
    assert "*" not in allow_methods


def test_frontend_policy_hashes_inline_scripts_however_the_tag_is_written():
    import base64
    import hashlib

    from app.core.security_headers import frontend_content_security_policy

    def source(body: str) -> str:
        return "'sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode() + "'"

    html = (
        "<html><head>"
        "<script>a();</script>"
        '<SCRIPT type="text/javascript">\n  b();\n</SCRIPT>'
        '<script type="module" src="/assets/index.js"></script>'
        "</head></html>"
    )
    script_src = frontend_content_security_policy(html).split("script-src ", 1)[1].split(";", 1)[0]

    assert source("a();") in script_src
    assert source("\n  b();\n") in script_src
    # An external script is allowed by 'self', not by a hash of its empty body.
    assert source("") not in script_src
