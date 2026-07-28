"""TypeScript/JavaScript outbound HTTP call sites (#209).

``fetch`` and axios differ from the Python clients in one important way: they are
plain identifiers, so the generic ``call`` pass already sees them. These tests
pin both halves of that — the proven sites become one service-interaction fact
instead of a generic call, and the unproven ones keep the existing behaviour.
"""

from __future__ import annotations

import pytest

from app.extraction.base import RI_EXT_UNSUPPORTED
from app.extraction.typescript import TypeScriptExtractor


def _extract(source: str, path: str = "src/api.ts"):
    return TypeScriptExtractor().extract(path, source.encode("utf-8"))


def _http_calls(result):
    return [
        (item.referent_text, item.evidence.start_line)
        for item in result.observations
        if item.observed_kind == "http_call"
    ]


def _generic_calls(result):
    return [
        (item.observed_kind, item.referent_text, item.evidence.start_line)
        for item in result.observations
        if item.observed_kind in ("call", "call_shadowed")
    ]


def _services(result):
    return sorted({node.stable_key for node in result.nodes if node.node_kind == "service"})


def _unsupported(result):
    return [item.message for item in result.diagnostics if item.code == RI_EXT_UNSUPPORTED]


# --- proven destinations ----------------------------------------------------


def test_fetch_without_an_init_object_is_a_specified_get():
    result = _extract('const r = fetch("https://api.example.com/v1/users");\n')

    assert _http_calls(result) == [("GET|https://api.example.com|/v1/users", 1)]
    assert _services(result) == ["svc:https://api.example.com"]


def test_a_literal_method_in_an_inline_init_overrides_the_get_default():
    result = _extract('const r = fetch("https://api.example.com/v1", { method: "post" });\n')

    assert _http_calls(result) == [("POST|https://api.example.com|/v1", 1)]


def test_a_backtick_literal_without_substitutions_is_still_a_literal():
    result = _extract("const r = fetch(`https://api.example.com/v1`);\n")

    assert _http_calls(result) == [("GET|https://api.example.com|/v1", 1)]


@pytest.mark.parametrize("local", ["axios", "http", "apiClient"])
def test_axios_is_proven_by_its_default_import_under_any_local_name(local):
    result = _extract(f'import {local} from "axios";\n\n{local}.delete("https://api.example.com/v1/1");\n')

    assert _http_calls(result) == [("DELETE|https://api.example.com|/v1/1", 3)]


def test_an_axios_named_object_from_another_module_is_not_the_client():
    result = _extract('import axios from "./local-axios";\n\naxios.get("https://api.example.com/v1");\n')

    assert _http_calls(result) == []
    assert _unsupported(result) == []


def test_one_origin_is_one_service_with_a_language_neutral_record():
    result = _extract(
        'fetch("https://api.example.com/a");\nfetch("https://api.example.com/b");\n'
    )

    services = [node for node in result.nodes if node.node_kind == "service"]
    assert _services(result) == ["svc:https://api.example.com"]
    assert services[0].properties == services[1].properties == {"origin": "https://api.example.com"}
    assert services[0].language is None


def test_query_strings_never_enter_a_stored_fact():
    result = _extract('fetch("https://api.example.com/v1?token=secret");\n')

    referent, _ = _http_calls(result)[0]
    assert referent == "GET|https://api.example.com|/v1"
    assert "secret" not in referent


# --- the generic call pass --------------------------------------------------


def test_a_proven_fetch_site_replaces_its_generic_call_rather_than_adding_to_it():
    result = _extract('fetch("https://api.example.com/v1");\n')

    assert _http_calls(result) == [("GET|https://api.example.com|/v1", 1)]
    assert _generic_calls(result) == []


def test_an_unproven_fetch_site_keeps_the_existing_generic_call_behaviour():
    result = _extract("export function f(u: string) {\n  return fetch(u);\n}\n")

    assert _http_calls(result) == []
    assert _generic_calls(result) == [("call", "fetch", 2)]


def test_an_unrelated_identifier_call_is_untouched():
    result = _extract("function helper() {}\nhelper();\n")

    assert _generic_calls(result) == [("call", "helper", 2)]


# --- disclosures ------------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "message"),
    [
        ("fetch(target)", "dynamic HTTP destination is unsupported"),
        ("fetch(`https://${target}/v1`)", "dynamic HTTP destination is unsupported"),
        ("fetch()", "dynamic HTTP destination is unsupported"),
        ('fetch("/v1/users")', "HTTP destination without an absolute http(s) URL is unsupported"),
        ('fetch("ws://api.example.com/v1")', "HTTP destination without an absolute http(s) URL is unsupported"),
        ('fetch("https://api.example.com/v1", init)', "computed fetch init is unsupported"),
        ('fetch("https://api.example.com/v1", { ...init })', "computed fetch init is unsupported"),
        ('fetch("https://api.example.com/v1", { method: verb })', "computed fetch init is unsupported"),
    ],
)
def test_an_unproven_call_site_is_disclosed_and_claims_nothing(call, message):
    result = _extract(f"export function f(target: string, init: RequestInit, verb: string) {{\n  return {call};\n}}\n")

    assert _http_calls(result) == []
    assert _services(result) == []
    assert _unsupported(result) == [message]


def test_a_shadowed_fetch_binding_is_disclosed_rather_than_trusted():
    result = _extract(
        "export function f() {\n"
        "  const fetch = (u: string) => u;\n"
        '  return fetch("https://api.example.com/v1");\n'
        "}\n"
    )

    assert _http_calls(result) == []
    assert _unsupported(result) == ["HTTP client name is shadowed by a local binding"]


def test_a_shadowed_axios_binding_is_disclosed_rather_than_trusted():
    result = _extract(
        'import axios from "axios";\n\n'
        "export function f(axios: { get(u: string): void }) {\n"
        '  return axios.get("https://api.example.com/v1");\n'
        "}\n"
    )

    assert _http_calls(result) == []
    assert _unsupported(result) == ["HTTP client name is shadowed by a local binding"]


@pytest.mark.parametrize("call", ['axios({ url: "https://api.example.com/v1" })', "axios.request(config)"])
def test_axios_call_forms_this_extractor_does_not_interpret_are_disclosed(call):
    result = _extract(f'import axios from "axios";\n\nexport function f(config: object) {{\n  return {call};\n}}\n')

    assert _http_calls(result) == []
    assert _unsupported(result) == ["unsupported HTTP client call form"]


def test_axios_create_is_not_mistaken_for_a_request():
    result = _extract('import axios from "axios";\n\nconst client = axios.create({ baseURL: "https://a.example.com" });\n')

    assert _http_calls(result) == []
    # A base URL is configuration, not a proven call destination.
    assert _services(result) == []


# --- determinism ------------------------------------------------------------


def test_repeated_extraction_is_byte_identical():
    source = (
        'import client from "axios";\n\n'
        "export async function load() {\n"
        '  await fetch("https://api.example.com/v1", { method: "PUT" });\n'
        '  return client.get("https://api.example.com/v2");\n'
        "}\n"
    )

    assert _extract(source) == _extract(source)
