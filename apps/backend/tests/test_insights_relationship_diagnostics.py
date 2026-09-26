"""Unit tests for the repository-insights unresolved-relationship split."""

from __future__ import annotations

from app.insights.relationship_diagnostics import (
    SHADOWED_CALL_MESSAGE,
    UnresolvedDisposition,
    UnresolvedRelationshipContext,
    classify_unresolved,
    split_unresolved_relationships,
)

_DJANGO_KEY = "dep:pypi:django"
_REACT_KEY = "dep:npm:react"


def _ctx(*, kinds=None, referents=None, bindings=None, deps=frozenset(), files=frozenset()):
    directories = frozenset(
        "/".join(parts[:count]) for parts in (path.split("/") for path in files) for count in range(1, len(parts))
    )
    return UnresolvedRelationshipContext(
        observed_kind_by_observation=kinds or {},
        referent_by_observation=referents or {},
        import_specifier_by_local_name=bindings or {},
        declared_dependency_keys=deps,
        file_paths=frozenset(files),
        directory_paths=directories,
    )


def _split(diagnostics, *, kinds=None, referents=None, bindings=None, deps=frozenset(), files=frozenset()):
    ctx = _ctx(kinds=kinds, referents=referents, bindings=bindings, deps=deps, files=files)
    return split_unresolved_relationships([(path, oid, None) for path, oid in diagnostics], ctx)


def test_stdlib_and_declared_dependency_imports_are_external():
    split = _split(
        [("app/a.py", "o1"), ("app/a.py", "o2"), ("app/a.py", "o3")],
        kinds={"o1": "import", "o2": "import", "o3": "import"},
        referents={"o1": "pathlib.Path", "o2": "django.db.models", "o3": "__future__.annotations"},
        deps=frozenset({_DJANGO_KEY}),
    )
    assert split == split.__class__(in_repo_gap=0, external_reference=3)


def test_relative_and_undeclared_imports_stay_in_repo_gaps():
    split = _split(
        [("app/a.py", "o1"), ("app/a.py", "o2")],
        kinds={"o1": "import", "o2": "import"},
        # A relative import and a bare package the repo never declares both
        # still look like they should have been an in-repo reference.
        referents={"o1": ".sibling.helper", "o2": "somevendorlib.client"},
    )
    assert split.in_repo_gap == 2
    assert split.external_reference == 0


def test_call_bound_to_an_external_module_is_an_external_reference():
    split = _split(
        [("web/app.py", "c1"), ("web/app.py", "c2")],
        kinds={"c1": "call", "c2": "call"},
        referents={"c1": "jsonify", "c2": "reconcile"},
        # jsonify is imported from flask (declared); reconcile has no binding.
        bindings={"web/app.py": {"jsonify": "flask"}},
        deps=frozenset({"dep:pypi:flask"}),
    )
    assert split.external_reference == 1
    assert split.in_repo_gap == 1


def test_bare_python_builtin_call_with_no_binding_is_external():
    # An already-sealed pre-#392 snapshot still has these recorded.
    split = _split(
        [("m.py", "b1"), ("m.py", "b2"), ("m.py", "b3")],
        kinds={"b1": "call", "b2": "call", "b3": "call"},
        referents={"b1": "len", "b2": "print", "b3": "helper_defined_nowhere"},
    )
    assert split.external_reference == 2
    assert split.in_repo_gap == 1


def test_js_test_runner_globals_are_external_only_in_js_files():
    split = _split(
        [("web/x.test.tsx", "j1"), ("web/x.test.tsx", "j2"), ("api/x.py", "j3")],
        kinds={"j1": "call", "j2": "call", "j3": "call"},
        referents={"j1": "expect", "j2": "describe", "j3": "expect"},
    )
    # expect/describe are ambient in the .tsx test; the same name in a .py file
    # is not a Python builtin, so it stays a gap.
    assert split.external_reference == 2
    assert split.in_repo_gap == 1


def test_unknown_observation_or_missing_path_counts_as_a_gap():
    split = _split(
        [("app/a.py", "missing"), (None, "c1")],
        kinds={"c1": "call"},
        referents={"c1": "len"},
    )
    assert split.in_repo_gap == 2
    assert split.external_reference == 0


def test_non_reference_kinds_are_never_reclassified():
    # http_call / iac_resource / dependency unresolveds are genuine gaps.
    split = _split(
        [("infra/main.tf", "h1")],
        kinds={"h1": "iac_resource"},
        referents={"h1": "aws_s3_bucket.logs"},
    )
    assert split.in_repo_gap == 1
    assert split.external_reference == 0


def test_total_always_equals_the_diagnostic_count():
    diagnostics = [(f"f{i}.py", f"o{i}") for i in range(20)]
    kinds = {f"o{i}": "call" for i in range(20)}
    referents = {f"o{i}": ("len" if i % 2 else "local_thing") for i in range(20)}
    split = _split(diagnostics, kinds=kinds, referents=referents)
    assert split.total == 20
    assert split.external_reference == 10
    assert split.in_repo_gap == 10


def test_a_shadowed_call_is_a_local_binding_not_a_gap():
    ctx = _ctx(kinds={"o1": "call"}, referents={"o1": "setOpen"})

    assert classify_unresolved("src/a.tsx", "o1", ctx, SHADOWED_CALL_MESSAGE) is UnresolvedDisposition.LOCAL_BINDING
    # The same call without the resolver's shadow message is still a gap.
    assert classify_unresolved("src/a.tsx", "o1", ctx, "calls has no resolvable target") is UnresolvedDisposition.GAP

    split = split_unresolved_relationships([("src/a.tsx", "o1", SHADOWED_CALL_MESSAGE)], ctx)
    assert (split.in_repo_gap, split.external_reference, split.local_binding) == (0, 0, 1)
    assert split.total == 1


def test_path_alias_import_naming_an_in_repo_file_is_not_a_gap():
    files = {"web/src/lib/utils.ts", "web/src/hooks/useAuth.tsx", "web/src/routes/index.tsx"}
    ctx = _ctx(
        kinds={"a": "import", "b": "import", "c": "import"},
        referents={"a": "@/lib/utils", "b": "@/hooks/useAuth", "c": "@/lib/missing"},
        files=files,
    )

    assert classify_unresolved("web/src/routes/index.tsx", "a", ctx) is UnresolvedDisposition.IN_REPO_TARGET_EXISTS
    assert classify_unresolved("web/src/routes/index.tsx", "b", ctx) is UnresolvedDisposition.IN_REPO_TARGET_EXISTS
    # An alias whose target is nowhere in the repository is a real broken import.
    assert classify_unresolved("web/src/routes/index.tsx", "c", ctx) is UnresolvedDisposition.GAP
    # A same-named file in an unrelated package does not vouch for it.
    assert classify_unresolved("other/src/x.tsx", "a", ctx) is UnresolvedDisposition.GAP


def test_alias_to_a_barrel_directory_is_not_a_gap():
    """A re-export-only ``index.ts`` leaves no node or evidence of its own; the
    directory of scanned files beside it is the available proof."""

    ctx = _ctx(
        kinds={"a": "import"},
        referents={"a": "@/shared/services/api"},
        files={"web/src/shared/services/api/client.ts", "web/src/app.tsx"},
    )

    assert classify_unresolved("web/src/app.tsx", "a", ctx) is UnresolvedDisposition.IN_REPO_TARGET_EXISTS


def test_call_bound_to_an_unresolved_alias_import_follows_the_import():
    ctx = _ctx(
        kinds={"call": "call"},
        referents={"call": "cn"},
        bindings={"web/src/a.tsx": {"cn": "@/lib/utils"}},
        files={"web/src/lib/utils.ts", "web/src/a.tsx"},
    )

    assert classify_unresolved("web/src/a.tsx", "call", ctx) is UnresolvedDisposition.IN_REPO_TARGET_EXISTS


def test_python_absolute_import_from_a_subdirectory_package_root():
    ctx = _ctx(
        kinds={"a": "import", "b": "import"},
        referents={"a": "app.api.deps.SessionDep", "b": "app.api.nope.Thing"},
        files={"backend/app/api/deps.py", "backend/app/api/routes/items.py"},
    )

    assert (
        classify_unresolved("backend/app/api/routes/items.py", "a", ctx) is UnresolvedDisposition.IN_REPO_TARGET_EXISTS
    )
    assert classify_unresolved("backend/app/api/routes/items.py", "b", ctx) is UnresolvedDisposition.GAP


def test_asset_and_loader_query_imports_are_not_code_relationships():
    ctx = _ctx(
        kinds={"a": "import", "b": "import", "c": "import", "d": "import"},
        referents={
            "a": "@/assets/logo.png",
            "b": "./styles/globals.css",
            "c": "./generated.ts?raw",
            "d": "./missing-module",
        },
    )

    for oid in ("a", "b", "c"):
        assert classify_unresolved("web/src/a.tsx", oid, ctx) is UnresolvedDisposition.NON_CODE_ASSET
    assert classify_unresolved("web/src/a.tsx", "d", ctx) is UnresolvedDisposition.GAP


def test_import_name_that_differs_from_the_declared_distribution_is_external():
    ctx = _ctx(
        kinds={"a": "import", "b": "import"},
        referents={"a": "jwt.exceptions.InvalidTokenError", "b": "yaml"},
        deps=frozenset({"dep:pypi:pyjwt"}),
    )

    assert classify_unresolved("app/a.py", "a", ctx) is UnresolvedDisposition.EXTERNAL
    # Aliases only help when the distribution is actually declared.
    assert classify_unresolved("app/a.py", "b", ctx) is UnresolvedDisposition.GAP
