"""Docker Compose resource extraction (#209).

An IaC resource fact claims that a named piece of infrastructure is declared at
an exact place in an exact manifest. These tests pin that claim, and pin the
boundary where a value stops being observed and becomes a template.
"""

from __future__ import annotations

import pytest

from app.extraction.base import (
    RI_EXT_UNSUPPORTED,
    RI_SEC_PATH_ESCAPE,
    RI_SRC_BINARY,
    RI_SRC_MALFORMED,
)
from app.extraction.iac import COMPOSE_RESOURCE_SECTIONS, IacExtractor
from app.extraction.support_matrix import supported_iac_filenames

COMPOSE = b"""services:
  api:
    image: python:3.13-slim
    ports:
      - "8000:8000"
  worker:
    image: ${WORKER_IMAGE}
  bare:
volumes:
  pgdata:
networks:
  backend:
    driver: bridge
"""


def _extract(path: str, source: bytes):
    return IacExtractor().extract(path, source)


def _nodes(result):
    return {node.stable_key: node for node in result.nodes}


# --- supports() -------------------------------------------------------------


def test_only_the_documented_compose_filenames_are_read():
    extractor = IacExtractor()

    assert set(supported_iac_filenames()) == {
        "compose.yaml",
        "compose.yml",
        "docker-compose.yaml",
        "docker-compose.yml",
    }
    assert extractor.supports("deploy/docker-compose.yml")
    assert extractor.supports("compose.yaml")
    # Treating an arbitrary YAML file as infrastructure would turn any document
    # with a ``services:`` key into a fabricated resource claim.
    assert not extractor.supports("config/settings.yaml")
    assert not extractor.supports("main.tf")
    assert not extractor.supports("k8s/deployment.yaml")
    assert not extractor.supports("Chart.yaml")


# --- resources --------------------------------------------------------------


def test_declared_resources_carry_their_type_name_and_exact_line():
    result = _extract("deploy/docker-compose.yml", COMPOSE)
    nodes = _nodes(result)

    assert set(COMPOSE_RESOURCE_SECTIONS.values()) == {"service", "volume", "network"}
    assert nodes["iac:deploy/docker-compose.yml::service/api"].evidence[0].start_line == 2
    assert nodes["iac:deploy/docker-compose.yml::service/worker"].evidence[0].start_line == 6
    assert nodes["iac:deploy/docker-compose.yml::service/bare"].evidence[0].start_line == 8
    assert nodes["iac:deploy/docker-compose.yml::volume/pgdata"].evidence[0].start_line == 10
    assert nodes["iac:deploy/docker-compose.yml::network/backend"].evidence[0].start_line == 12
    for node in result.nodes:
        assert node.node_kind == "iac_resource"
        assert node.evidence[0].start_line == node.evidence[0].end_line
        assert node.properties["manifest_path"] == "deploy/docker-compose.yml"
        assert node.properties["manifest_format"] == "docker-compose"


def test_identity_includes_the_manifest_so_two_files_declare_two_resources():
    first = _extract("a/docker-compose.yml", b"services:\n  db:\n    image: postgres:17\n")
    second = _extract("b/docker-compose.yml", b"services:\n  db:\n    image: postgres:17\n")

    assert first.nodes[0].stable_key == "iac:a/docker-compose.yml::service/db"
    assert second.nodes[0].stable_key == "iac:b/docker-compose.yml::service/db"


def test_a_literal_image_is_recorded_and_a_templated_one_is_disclosed():
    result = _extract("deploy/docker-compose.yml", COMPOSE)
    nodes = _nodes(result)

    assert nodes["iac:deploy/docker-compose.yml::service/api"].properties["image"] == "python:3.13-slim"
    # The property is withheld rather than storing "${WORKER_IMAGE}" as if it
    # were the image that actually runs.
    assert "image" not in nodes["iac:deploy/docker-compose.yml::service/worker"].properties
    templated = [
        diagnostic for diagnostic in result.diagnostics if diagnostic.message == "templated IaC value is unsupported"
    ]
    assert len(templated) == 1
    assert templated[0].code == RI_EXT_UNSUPPORTED
    assert templated[0].span == (6, 6)
    assert templated[0].subject == "iac:deploy/docker-compose.yml::service/worker"


@pytest.mark.parametrize("image", [b"${TAG}", b"registry/app:${TAG}", b"$TAG", b"${TAG:-latest}"])
def test_every_interpolation_form_withholds_the_image(image):
    result = _extract("docker-compose.yml", b"services:\n  api:\n    image: " + image + b"\n")

    assert "image" not in result.nodes[0].properties
    assert any(diagnostic.code == RI_EXT_UNSUPPORTED for diagnostic in result.diagnostics)


def test_an_escaped_dollar_is_a_literal_not_a_template():
    result = _extract("docker-compose.yml", b"services:\n  api:\n    image: app:$$literal\n")

    assert result.nodes[0].properties["image"] == "app:$$literal"
    assert result.diagnostics == ()


def test_a_service_without_a_body_is_still_a_declared_resource():
    nodes = _nodes(_extract("deploy/docker-compose.yml", COMPOSE))

    bare = nodes["iac:deploy/docker-compose.yml::service/bare"]
    assert bare.name == "bare"
    assert "image" not in bare.properties


def test_unsupported_compose_sections_contribute_no_resources():
    result = _extract(
        "docker-compose.yml",
        b"configs:\n  app:\n    file: ./app.conf\nsecrets:\n  token:\n    file: ./token\n",
    )

    assert result.nodes == ()
    assert result.diagnostics == ()


# --- observations -----------------------------------------------------------


def test_each_resource_emits_a_typed_observation_about_itself():
    result = _extract("docker-compose.yml", b"services:\n  api:\n    image: nginx:1.27\nvolumes:\n  data:\n")

    assert [
        (item.observed_kind, item.subject_kind, item.subject_key, item.referent_text, item.ordinal)
        for item in result.observations
    ] == [
        ("iac_resource", "iac_resource", "iac:docker-compose.yml::service/api", "service/api", 1),
        ("iac_resource", "iac_resource", "iac:docker-compose.yml::volume/data", "volume/data", 1),
    ]


# --- failure paths ----------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        b"services:\n  api:\n   image: x\n  bad\n",
        b"services:\n  - api\n",
        b"- just\n- a\n- list\n",
        b"services:\n  api: nginx:1.27\n",
        b"services:\n  ? [a, b]\n  : value\n",
        b"---\nservices:\n  a:\n    image: x\n---\nservices:\n  b:\n    image: y\n",
    ],
)
def test_structurally_invalid_manifests_fail_closed_with_one_diagnostic(source):
    result = _extract("docker-compose.yml", source)

    assert result.nodes == ()
    assert result.observations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SRC_MALFORMED]


def test_an_empty_manifest_claims_nothing_without_complaining():
    result = _extract("docker-compose.yml", b"")

    assert result.nodes == ()
    assert result.diagnostics == ()


def test_a_binary_manifest_is_excluded_from_line_addressed_extraction():
    result = _extract("docker-compose.yml", b"services:\x00\n")

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SRC_BINARY]


def test_undecodable_bytes_are_reported_as_malformed_source():
    result = _extract("docker-compose.yml", b"\xff\xfeservices:")

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SRC_MALFORMED]


def test_a_path_escaping_the_repository_root_is_rejected_before_extraction():
    result = _extract("../../docker-compose.yml", COMPOSE)

    assert result.nodes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [RI_SEC_PATH_ESCAPE]


# --- determinism ------------------------------------------------------------


def test_repeated_extraction_is_byte_identical_and_key_order_independent():
    ordered = b"services:\n  api:\n    image: a:1\n  web:\n    image: b:2\n"
    assert _extract("docker-compose.yml", ordered) == _extract("docker-compose.yml", ordered)

    reordered = b"services:\n  web:\n    image: b:2\n  api:\n    image: a:1\n"
    # Emission order is a function of identity, so only the spans differ.
    assert [node.stable_key for node in _extract("docker-compose.yml", ordered).nodes] == [
        node.stable_key for node in _extract("docker-compose.yml", reordered).nodes
    ]
