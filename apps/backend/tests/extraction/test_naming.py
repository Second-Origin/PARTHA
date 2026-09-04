from app.extraction.naming import DiscriminatorAssigner, package_root, symbol_stable_key


def test_symbol_stable_key_builds_qualified_dotted_name():
    assert symbol_stable_key("src/auth/service.ts", [], "issueToken") == "src/auth/service.ts::issueToken"
    assert (
        symbol_stable_key("src/auth/service.ts", ["AuthService"], "login") == "src/auth/service.ts::AuthService.login"
    )
    assert symbol_stable_key("app/api/auth.py", ["outer"], "_inner") == "app/api/auth.py::outer._inner"


def test_package_root_reads_the_leading_python_module_from_a_dotted_specifier():
    assert package_root("django", "server/wsgi.py") == "django"
    assert package_root("django.core.wsgi.get_wsgi_application", "server/wsgi.py") == "django"
    assert package_root("os", "server/wsgi.py") == "os"


def test_package_root_reports_no_package_for_a_python_relative_import():
    # A relative import (from .models import User -> ".models.User") can
    # never be an external package -- the leading dot splits to an empty
    # root, which must never accidentally match a real dependency name.
    assert package_root(".models.User", "app/views.py") == ""


def test_package_root_reads_the_leading_js_segment_including_scoped_packages():
    assert package_root("react", "src/app.tsx") == "react"
    assert package_root("@scope/name/sub/path", "src/app.tsx") == "@scope/name"
    assert package_root("./util", "src/app.tsx") == "."
    assert package_root("../models/user", "src/app.tsx") == ".."


def test_discriminator_numbers_duplicates_in_source_order():
    assigner = DiscriminatorAssigner()
    base = "a.ts::fmt"
    assert assigner.key(base) == ("a.ts::fmt", False)
    assert assigner.key(base) == ("a.ts::fmt#2", True)
    assert assigner.key(base) == ("a.ts::fmt#3", True)
    # a different key is independent
    assert assigner.key("a.ts::other") == ("a.ts::other", False)
