"""FastAPI authentication idioms the explanation must recognise (#471).

The first cut only understood ``def handler(user=Depends(guard))``. Real
FastAPI code (this layout follows the official full-stack template) also
guards routes with ``dependencies=[...]`` on the decorator or on the router.
Each fixture below is driven through a real analysis so extraction,
resolution, classification and the explanation agree end to end.
"""

from __future__ import annotations

import io
import zipfile

from tests.analysis_helpers import run_analysis_jobs

_INIT = b""

_DEPS = (
    b"from typing import Annotated\n\n"
    b"from fastapi import Depends\n"
    b"from fastapi.security import OAuth2PasswordBearer\n\n"
    b'reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="login")\n\n\n'
    b"def get_db():\n    yield None\n\n\n"
    b"SessionDep = Annotated[object, Depends(get_db)]\n"
    b"TokenDep = Annotated[str, Depends(reusable_oauth2)]\n\n\n"
    b"def get_current_user(session: SessionDep, token: TokenDep) -> dict:\n"
    b"    return {}\n\n\n"
    b"CurrentUser = Annotated[dict, Depends(get_current_user)]\n\n\n"
    b"def get_current_active_superuser(current_user: CurrentUser) -> dict:\n"
    b"    return current_user\n"
)

_FILES = {
    "README.md": b"# fastapi auth fixture\n",
    "backend/app/__init__.py": _INIT,
    "backend/app/api/__init__.py": _INIT,
    "backend/app/api/routes/__init__.py": _INIT,
    "backend/app/api/deps.py": _DEPS,
    # Guard through dependencies=[...] on the route decorator.
    "backend/app/api/routes/utils.py": (
        b"from fastapi import APIRouter, Depends\n\n"
        b"from app.api.deps import get_current_active_superuser\n\n"
        b"router = APIRouter()\n\n\n"
        b'@router.post("/test-email/", dependencies=[Depends(get_current_active_superuser)])\n'
        b"def test_email() -> dict:\n"
        b"    return {}\n\n\n"
        b'@router.get("/health-check/")\n'
        b"def health_check() -> bool:\n"
        b"    return True\n"
    ),
    # Guard through dependencies=[...] on the router itself.
    "backend/app/api/routes/admin.py": (
        b"from fastapi import APIRouter, Depends\n\n"
        b"from app.api.deps import get_current_active_superuser\n\n"
        b'router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_active_superuser)])\n\n\n'
        b'@router.get("/users")\n'
        b"def list_users() -> list:\n"
        b"    return []\n\n\n"
        b'@router.delete("/users/{user_id}")\n'
        b"def delete_user(user_id: int) -> None:\n"
        b"    return None\n"
    ),
}


def _analyse(auth_client, files: dict[str, bytes]) -> dict:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    response = auth_client.post(
        "/repositories/upload",
        files={"file": ("fastapi-auth.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 201, response.text
    repository = response.json()
    assert auth_client.post(f"/analysis/{repository['id']}/start").status_code == 200
    assert run_analysis_jobs() == 1
    explanation = auth_client.get(f"/analysis/{repository['id']}/architecture/authentication")
    assert explanation.status_code == 200, explanation.text
    return explanation.json()


def _claim_names(body: dict, kind: str) -> set[str]:
    return {claim["name"] for claim in body["claims"] if claim["kind"] == kind}


def test_guarded_routes_are_found_through_decorator_and_router_dependencies(auth_client):
    body = _analyse(auth_client, _FILES)

    # Route names are the decorator's own path literal (a router prefix is not
    # folded in), so the admin router's routes read "/users...".
    assert _claim_names(body, "route") == {"/test-email/", "/users", "/users/{user_id}"}
    # A route with no guard anywhere is not authentication.
    assert "/health-check/" not in _claim_names(body, "route")
    assert _claim_names(body, "middleware") == {"get_current_active_superuser"}
    pairs = {(r["subject"], r["predicate"], r["object"]) for r in body["relationships"]}
    assert ("test_email", "injects", "get_current_active_superuser") in pairs
    assert ("list_users", "injects", "get_current_active_superuser") in pairs
    assert ("delete_user", "injects", "get_current_active_superuser") in pairs
    assert all(relationship["evidence"] for relationship in body["relationships"])


def test_a_router_dependency_only_guards_that_routers_routes(auth_client):
    files = dict(_FILES)
    files["backend/app/api/routes/public.py"] = (
        b"from fastapi import APIRouter\n\n"
        b"public = APIRouter()\n\n\n"
        b'@public.get("/open")\n'
        b"def open_route() -> bool:\n"
        b"    return True\n"
    )

    body = _analyse(auth_client, files)

    assert "/open" not in _claim_names(body, "route")


def test_a_non_guard_dependency_on_a_decorator_is_not_authentication(auth_client):
    files = {
        "README.md": b"# fixture\n",
        "app/__init__.py": _INIT,
        "app/deps.py": b"def get_db():\n    yield None\n",
        "app/routes.py": (
            b"from fastapi import APIRouter, Depends\n\n"
            b"from app.deps import get_db\n\n"
            b"router = APIRouter()\n\n\n"
            b'@router.get("/things", dependencies=[Depends(get_db)])\n'
            b"def things() -> list:\n"
            b"    return []\n"
        ),
    }

    body = _analyse(auth_client, files)

    assert _claim_names(body, "route") == set()
