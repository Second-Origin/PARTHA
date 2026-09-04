"""Unit coverage for the unresolved-import disposition rules (#412).

End-to-end coverage (a real repository, a real sealed snapshot, a real
Engineering Review response) lives in test_engineering_review_v2.py. This
file is scoped to the pure decision functions themselves.
"""

from app.review.import_dispositions import (
    NODE_BUILTIN_MODULES,
    PYTHON_STDLIB_MODULES,
    declared_dependency_key,
    is_platform_import,
    is_recognized_external_import,
)


def test_python_stdlib_modules_includes_the_common_offenders():
    # These are exactly the Django-boilerplate imports (asgi.py/wsgi.py/
    # settings.py/urls.py/manage.py) that motivated this fix.
    for name in ("os", "sys", "pathlib", "json", "re", "typing", "collections"):
        assert name in PYTHON_STDLIB_MODULES


def test_node_builtin_modules_covers_the_common_ones():
    for name in ("fs", "path", "http", "crypto", "os", "url"):
        assert name in NODE_BUILTIN_MODULES
    # A Python stdlib name is not automatically a Node builtin, or vice versa.
    assert "pathlib" not in NODE_BUILTIN_MODULES


def test_is_platform_import_recognizes_python_stdlib_by_package_root():
    assert is_platform_import("os", "app.py") is True
    assert is_platform_import("django.core.wsgi.get_wsgi_application", "app.py") is False
    assert is_platform_import("pathlib.Path", "app.py") is True


def test_is_platform_import_recognizes_node_builtins_with_and_without_prefix():
    assert is_platform_import("fs", "src/app.ts") is True
    assert is_platform_import("node:fs", "src/app.ts") is True
    assert is_platform_import("node:fs/promises", "src/app.ts") is True
    assert is_platform_import("react", "src/app.ts") is False


def test_is_platform_import_never_matches_a_relative_import():
    assert is_platform_import(".models.User", "app/views.py") is False
    assert is_platform_import("./util", "src/app.ts") is False


def test_declared_dependency_key_is_none_for_a_relative_import():
    assert declared_dependency_key(".models.User", "app/views.py") is None
    assert declared_dependency_key("./util", "src/app.ts") is None


def test_declared_dependency_key_normalizes_pypi_names_like_the_resolver_does():
    # "Django" and "django" (and "django_rest-framework" style separators)
    # must land on the same key a manifest declaration would produce, or a
    # real declared dependency would still fail to match by pure casing.
    assert declared_dependency_key("django.core.wsgi", "app.py") == "dep:pypi:django"
    assert declared_dependency_key("Django", "app.py") == "dep:pypi:django"


def test_declared_dependency_key_uses_npm_ecosystem_for_non_python_files():
    assert declared_dependency_key("react", "src/app.ts") == "dep:npm:react"
    assert declared_dependency_key("@scope/name/sub", "src/app.ts") == "dep:npm:@scope/name"


def test_is_recognized_external_import_true_for_platform_regardless_of_declared_keys():
    assert is_recognized_external_import("os", "app.py", frozenset()) is True


def test_is_recognized_external_import_true_only_when_declared():
    declared = frozenset({"dep:pypi:django"})
    assert is_recognized_external_import("django.core.wsgi", "app.py", declared) is True
    assert is_recognized_external_import("flask", "app.py", declared) is False


def test_is_recognized_external_import_false_for_a_relative_import_even_with_matching_declared_keys():
    # A pathological but real guard: an empty package root must never match
    # anything, even if a dependency named "" somehow existed in the set.
    declared = frozenset({"dep:pypi:"})
    assert is_recognized_external_import(".models.User", "app/views.py", declared) is False
