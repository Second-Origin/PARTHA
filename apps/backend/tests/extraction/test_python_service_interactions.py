"""Python outbound HTTP call sites (#209).

The contract these tests hold the extractor to: a destination fact exists only
when an import proves the client, a literal proves the method, and a literal
absolute URL proves the origin. Everything else is a disclosure.
"""

from __future__ import annotations

import pytest

from app.extraction.base import RI_EXT_UNSUPPORTED
from app.extraction.python import PythonExtractor


def _extract(source: str, path: str = "app/client.py"):
    return PythonExtractor().extract(path, source.encode("utf-8"))


def _http_calls(result):
    return [
        (item.referent_text, item.evidence.start_line)
        for item in result.observations
        if item.observed_kind == "http_call"
    ]


def _services(result):
    return sorted({node.stable_key for node in result.nodes if node.node_kind == "service"})


def _unsupported(result):
    return [item.message for item in result.diagnostics if item.code == RI_EXT_UNSUPPORTED]


# --- proven destinations ----------------------------------------------------


def test_a_requests_module_call_names_its_method_origin_and_path():
    result = _extract('import requests\n\nrequests.get("https://api.example.com/v1/users")\n')

    assert _http_calls(result) == [("GET|https://api.example.com|/v1/users", 3)]
    assert _services(result) == ["svc:https://api.example.com"]


def test_an_aliased_module_import_still_proves_the_client():
    result = _extract('import httpx as hx\n\nhx.post("https://api.example.com/v1/users", json={})\n')

    assert _http_calls(result) == [("POST|https://api.example.com|/v1/users", 3)]


@pytest.mark.parametrize(
    "setup",
    [
        "import requests\n\nclient = requests.Session()\n",
        "import httpx\n\nclient = httpx.Client()\n",
        "import httpx\n\nclient = httpx.AsyncClient()\n",
        "from requests import Session\n\nclient = Session()\n",
        "from httpx import Client\n\nclient = Client()\n",
    ],
)
def test_a_client_object_inherits_the_library_method_surface(setup):
    result = _extract(f'{setup}\nclient.get("https://api.example.com/health")\n')

    assert _http_calls(result) == [("GET|https://api.example.com|/health", setup.count("\n") + 2)]


def test_a_request_call_reads_its_method_from_a_literal_argument():
    positional = _extract('import requests\n\nrequests.request("DELETE", "https://api.example.com/v1/1")\n')
    keyword = _extract('import requests\n\nrequests.request(method="patch", url="https://api.example.com/v1/1")\n')

    assert _http_calls(positional) == [("DELETE|https://api.example.com|/v1/1", 3)]
    # The method token is canonicalized; the destination is not.
    assert _http_calls(keyword) == [("PATCH|https://api.example.com|/v1/1", 3)]


def test_a_url_keyword_argument_is_read_like_the_positional_one():
    result = _extract('import requests\n\nrequests.get(url="https://api.example.com/v1")\n')

    assert _http_calls(result) == [("GET|https://api.example.com|/v1", 3)]


def test_one_origin_is_one_service_however_many_call_sites_reach_it():
    result = _extract(
        'import requests\n\nrequests.get("https://api.example.com/a")\nrequests.post("https://api.example.com/b")\n'
    )

    assert _services(result) == ["svc:https://api.example.com"]
    assert len([node for node in result.nodes if node.node_kind == "service"]) == 2
    # Both emissions describe one entity, so their records must be identical
    # or the snapshot would refuse to seal them onto one key.
    services = [node for node in result.nodes if node.node_kind == "service"]
    assert services[0].properties == services[1].properties
    assert services[0].language is None


# --- origin normalization ---------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://API.Example.COM/v1", "GET|https://api.example.com|/v1"),
        ("https://api.example.com:443/v1", "GET|https://api.example.com|/v1"),
        ("http://api.example.com:80/v1", "GET|http://api.example.com|/v1"),
        ("https://api.example.com:8443/v1", "GET|https://api.example.com:8443|/v1"),
        ("https://api.example.com", "GET|https://api.example.com|/"),
    ],
)
def test_origins_are_normalized_so_one_service_has_one_identity(url, expected):
    result = _extract(f'import requests\n\nrequests.get("{url}")\n')

    assert _http_calls(result) == [(expected, 3)]


def test_query_strings_and_credentials_never_enter_a_stored_fact():
    result = _extract(
        'import requests\n\nrequests.get("https://user:pa55@api.example.com/v1/users?api_key=secret&x=1")\n'
    )

    referent, _ = _http_calls(result)[0]
    assert referent == "GET|https://api.example.com|/v1/users"
    assert "secret" not in referent and "pa55" not in referent
    assert _services(result) == ["svc:https://api.example.com"]


# --- disclosures ------------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "message"),
    [
        ("requests.get(target)", "dynamic HTTP destination is unsupported"),
        ('requests.get(f"https://{target}/v1")', "dynamic HTTP destination is unsupported"),
        ('requests.get("https://a.example.com/" + target)', "dynamic HTTP destination is unsupported"),
        ("requests.get()", "dynamic HTTP destination is unsupported"),
        ('requests.get("/v1/users")', "HTTP destination without an absolute http(s) URL is unsupported"),
        ('requests.get("//api.example.com/v1")', "HTTP destination without an absolute http(s) URL is unsupported"),
        ('requests.get("ftp://api.example.com/v1")', "HTTP destination without an absolute http(s) URL is unsupported"),
        ('requests.request(target, "https://api.example.com/v1")', "computed HTTP method is unsupported"),
    ],
)
def test_an_unproven_call_site_is_disclosed_and_claims_nothing(call, message):
    result = _extract(f"import requests\n\n\ndef f(target):\n    return {call}\n")

    assert _http_calls(result) == []
    assert _services(result) == []
    assert _unsupported(result) == [message]


def test_a_bare_imported_client_function_is_disclosed_not_counted_twice():
    """``get(url)`` is already a generic ``call``; a second fact would double-count it."""

    result = _extract('from requests import get\n\nget("https://api.example.com/v1")\n')

    assert _http_calls(result) == []
    assert _unsupported(result) == ["bare imported HTTP client function is unsupported"]
    assert [item.referent_text for item in result.observations if item.observed_kind == "call"] == ["get"]


def test_a_shadowed_client_name_is_disclosed_rather_than_trusted():
    result = _extract(
        "import requests\n\n\n"
        "def f():\n"
        "    requests = object()\n"
        '    return requests.get("https://api.example.com/v1")\n'
    )

    assert _http_calls(result) == []
    assert _unsupported(result) == ["HTTP client name is shadowed by a local binding"]


def test_a_local_client_object_shadowed_by_a_parameter_is_disclosed():
    result = _extract(
        "import httpx\n\n"
        "client = httpx.Client()\n\n\n"
        "def f(client):\n"
        '    return client.get("https://api.example.com/v1")\n'
    )

    assert _http_calls(result) == []
    assert _unsupported(result) == ["HTTP client name is shadowed by a local binding"]


def test_an_unrelated_object_with_a_get_method_is_not_an_http_client():
    result = _extract('import os\n\ncache = dict()\ncache.get("https://api.example.com/v1")\n')

    assert _http_calls(result) == []
    assert _unsupported(result) == []


def test_non_request_attributes_on_a_client_are_not_call_sites():
    result = _extract("import requests\n\nsession = requests.Session()\nsession.close()\nrequests.codes.ok\n")

    assert _http_calls(result) == []
    assert _unsupported(result) == []


# --- interaction with the generic call pass ---------------------------------


def test_attribute_form_client_calls_never_produced_a_generic_call_observation():
    result = _extract('import requests\n\nrequests.get("https://api.example.com/v1")\n')

    assert [item for item in result.observations if item.observed_kind in ("call", "call_shadowed")] == []


# --- determinism ------------------------------------------------------------


def test_repeated_extraction_is_byte_identical():
    source = (
        "import requests\n\n"
        "session = requests.Session()\n\n\n"
        "def f():\n"
        '    return session.request("PUT", "https://api.example.com/v1")\n'
    )

    assert _extract(source) == _extract(source)
