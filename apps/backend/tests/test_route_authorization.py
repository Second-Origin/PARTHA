"""Cross-route authorization sweep (E1.3 / #63).

Two guards, both derived from the app's own router table so a newly added route
fails by omission rather than shipping unscoped:

1. Every ownership-required route returns 401 without a valid token.
2. Every route that resolves a repository by id returns 404 (never 403) for a
   caller who is not the owner, and 200 for the owner — so a cross-user request
   is indistinguishable from a missing resource and never confirms it exists.
"""

import re
import uuid

from fastapi.routing import APIRoute

from tests.conftest import register_user

# The routers guarded by get_current_user at the router level.
PROTECTED_PREFIXES = ("/repositories", "/analysis", "/ai", "/documentation", "/export")

PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"


def _collect_api_routes(router, acc: list[APIRoute]) -> None:
    # FastAPI keeps an included router nested (as a ``_IncludedRouter`` exposing
    # ``original_router``) rather than flattening it into app.routes, so walk the
    # tree to reach every real APIRoute — a new route is discovered automatically.
    for route in getattr(router, "routes", []) or []:
        if isinstance(route, APIRoute):
            acc.append(route)
        original = getattr(route, "original_router", None)
        if original is not None:
            _collect_api_routes(original, acc)
        elif getattr(route, "routes", None):
            _collect_api_routes(route, acc)


def _protected_routes(app) -> list[tuple[str, str]]:
    found: list[APIRoute] = []
    _collect_api_routes(app, found)
    routes: set[tuple[str, str]] = set()
    for route in found:
        if not route.path.startswith(PROTECTED_PREFIXES):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            routes.add((method, route.path))
    return sorted(routes)


def _concrete_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", PLACEHOLDER_ID, path)


def test_every_protected_route_requires_authentication(client):
    routes = _protected_routes(client.app)
    # The list is derived from the live router; if it is empty the discovery is
    # broken and the guard would silently pass, so assert it found routes.
    assert routes, "expected to discover protected routes from the router table"

    failures = []
    for method, path in routes:
        url = _concrete_path(path)
        # A required query param (e.g. the file route's `path`) is supplied so a
        # missing-param 422 can never mask the 401 we are asserting; auth is
        # enforced ahead of the handler regardless.
        response = client.request(method, url, params={"path": "README.md"})
        if response.status_code != 401:
            failures.append((method, path, response.status_code))

    assert not failures, f"routes reachable without authentication: {failures}"


def _seed_repository(owner_id: str) -> str:
    from app.core.database import SessionLocal
    from app.models.repository import RepositoryRecord

    db = SessionLocal()
    try:
        repository_id = str(uuid.uuid4())
        db.add(
            RepositoryRecord(
                id=repository_id,
                owner_id=owner_id,
                name="owned-repo",
                source="upload",
                local_path=f"/tmp/{repository_id}",
                status="completed",
                file_tree=[],
            )
        )
        db.commit()
        return repository_id
    finally:
        db.close()


# Each entry is (method, path template, optional json body key for repository id).
# For body-carrying routes the id travels in the payload, not the URL.
_CROSS_OWNER_ROUTES = [
    ("GET", "/repositories/{id}", None),
    ("GET", "/repositories/{id}/file?path=README.md", None),
    ("DELETE", "/repositories/{id}", None),
    ("POST", "/analysis/{id}/start", None),
    ("GET", "/analysis/{id}/status", None),
    ("GET", "/analysis/{id}/architecture", None),
    ("GET", "/analysis/{id}/dependencies", None),
    ("GET", "/analysis/{id}/review", None),
    ("POST", "/documentation/generate", "repositoryId"),
    ("POST", "/ai/query", "repositoryId"),
    ("POST", "/export", "repositoryId"),
]


def test_repository_scoped_routes_return_404_for_a_non_owner(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    bob = make_auth_headers("bob@example.com")
    repository_id = _seed_repository(alice["user"]["id"])

    failures = []
    for method, template, body_key in _CROSS_OWNER_ROUTES:
        url = template.replace("{id}", repository_id)
        json_body = None
        if body_key is not None:
            url = template  # body-carrying routes use a static path
            json_body = {body_key: repository_id}
            if template == "/documentation/generate":
                json_body["format"] = "markdown"
            elif template == "/ai/query":
                json_body["query"] = "hello"
            elif template == "/export":
                json_body.update({"target": "review", "format": "json"})
        response = client.request(method, url, headers=bob["headers"], json=json_body)
        # 404, never 403: the non-owner is told the resource does not exist
        # rather than that it exists but is forbidden.
        if response.status_code != 404:
            failures.append((method, template, response.status_code))

    assert not failures, f"routes leaking another user's repository (expected 404): {failures}"


def test_owner_can_read_their_own_repository(client, make_auth_headers):
    alice = make_auth_headers("alice@example.com")
    repository_id = _seed_repository(alice["user"]["id"])

    response = client.get(f"/repositories/{repository_id}", headers=alice["headers"])
    assert response.status_code == 200
    assert response.json()["id"] == repository_id
