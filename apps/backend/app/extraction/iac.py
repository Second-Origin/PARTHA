"""Infrastructure-as-code resource extraction for supported manifests (#209).

Supported format — this list is exact:

Docker Compose (``compose.yaml``, ``compose.yml``, ``docker-compose.yaml``,
``docker-compose.yml``)
    The top-level ``services``, ``volumes``, and ``networks`` mappings are read.
    Each key in one of those mappings is a declared resource whose name is
    written literally in the source, so its identity and span are facts about the
    bytes rather than an inference.

Deliberately **not** supported, and reported as such rather than guessed at:
Terraform/OpenTofu HCL, Kubernetes manifests, Helm charts, CloudFormation,
Pulumi, Ansible, and Compose's ``configs``/``secrets`` sections. Detecting
Kubernetes by scanning every ``*.yaml`` for an ``apiVersion`` key would make an
arbitrary YAML file a resource claim, which is exactly the fabricated fact the
truth contract forbids; a fixed, documented filename set is the boundary.

Parsing goes through PyYAML's *composer* (``yaml.compose``) rather than
``safe_load``. The composer returns the node graph with each node's source
marks, which is what makes an exact one-based declaration line possible at all,
and it never constructs Python objects or expands aliases.

Values are only recorded when the source proves them. A service ``image`` that
interpolates an environment variable (``${TAG}``) is a template, not an observed
image, so it becomes an ``RI-EXT-UNSUPPORTED`` disclosure and the property is
omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
import posixpath
import re

import yaml

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_EXT_UNSUPPORTED,
    RI_SEC_PATH_ESCAPE,
    RI_SRC_MALFORMED,
    assign_ordinals,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.extraction.naming import iac_resource_stable_key
from app.extraction.structured import StructureError
from app.extraction.support_matrix import supported_iac_filenames
from app.intelligence import canonical

SUPPORTED_IAC_FILENAMES = supported_iac_filenames()

#: Top-level Compose mapping -> the singular resource type recorded for its keys.
COMPOSE_RESOURCE_SECTIONS = {
    "networks": "network",
    "services": "service",
    "volumes": "volume",
}

#: ``${VAR}``, ``${VAR:-default}``, and bare ``$VAR`` interpolation. Compose
#: escapes a literal dollar as ``$$``, so that form is not a template.
_INTERPOLATION = re.compile(r"(?<!\$)\$(?:\{[^}]*\}|[A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class _Resource:
    resource_type: str
    name: str
    line: int
    #: The declared image, only when it is a literal with no interpolation.
    image: str | None
    #: True when a value was skipped because it is templated, so the caller can
    #: disclose the blind spot at this exact resource.
    templated: bool


class IacExtractor:
    """Extract declared IaC resources from supported manifest formats."""

    name = "iac-manifest"
    version = "1.0.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return posixpath.basename(path) in SUPPORTED_IAC_FILENAMES

    def extract(self, path: str, source: bytes) -> ExtractionResult:
        text, source_diagnostic = decode_source(path, source, producer=self.producer)
        if text is None:
            assert source_diagnostic is not None  # decode_source pairs None text with a diagnostic
            return ExtractionResult(diagnostics=(source_diagnostic,))
        try:
            normalized_path = canonical.normalize_repo_path(path)
        except canonical.PathEscapeError:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SEC_PATH_ESCAPE,
                        category="path escape",
                        severity="error",
                        message="source path is absolute or escapes the repository root",
                    ),
                )
            )

        line_count = logical_line_count(text)
        file_subject = canonical.normalize_stable_key("file", f"file:{normalized_path}")
        try:
            resources = self._compose_resources(text)
        except (yaml.YAMLError, StructureError):
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SRC_MALFORMED,
                        category="malformed source",
                        severity="error",
                        message="IaC manifest could not be parsed or has an unsupported structure",
                        path=normalized_path,
                        subject=file_subject,
                    ),
                )
            )

        nodes: list[ExtractedNode] = []
        observations: list[ExtractedObservation] = []
        diagnostics: list[ExtractedDiagnostic] = []
        for resource in resources:
            stable_key = iac_resource_stable_key(normalized_path, resource.resource_type, resource.name)
            evidence, diagnostic = build_evidence(
                normalized_path,
                resource.line,
                resource.line,
                line_count,
                producer=self.producer,
            )
            if evidence is None:
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
                continue
            properties: dict[str, object] = {
                "resource_type": resource.resource_type,
                "manifest_format": "docker-compose",
                "manifest_path": normalized_path,
            }
            if resource.image is not None:
                properties["image"] = resource.image
            nodes.append(
                ExtractedNode(
                    node_kind="iac_resource",
                    stable_key=stable_key,
                    name=resource.name,
                    language=None,
                    evidence=(evidence,),
                    properties=properties,
                )
            )
            observations.append(
                ExtractedObservation(
                    observed_kind="iac_resource",
                    subject_kind="iac_resource",
                    subject_key=stable_key,
                    referent_text=f"{resource.resource_type}/{resource.name}",
                    ordinal=0,
                    evidence=evidence,
                )
            )
            if resource.templated:
                diagnostics.append(
                    ExtractedDiagnostic(
                        code=RI_EXT_UNSUPPORTED,
                        category="unsupported construct",
                        severity="info",
                        # Naming the construct only: the interpolated value can
                        # carry deployment detail, and RFC §13 keeps repository
                        # content out of diagnostic text. The span locates it.
                        message="templated IaC value is unsupported",
                        path=normalized_path,
                        span=(resource.line, resource.line),
                        subject=stable_key,
                    )
                )
        return ExtractionResult(
            nodes=tuple(nodes),
            observations=assign_ordinals(observations),
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _compose_resources(text: str) -> list[_Resource]:
        """Read declared Compose resources with their exact declaration lines.

        ``yaml.compose`` yields the node graph rather than constructed objects,
        so each mapping key keeps the source mark this needs. An empty document
        is a valid file with no resources; anything whose root or section is not
        a mapping is a structure this extractor refuses to interpret.
        """

        root = yaml.compose(text, Loader=yaml.SafeLoader)
        if root is None:
            return []
        if not isinstance(root, yaml.MappingNode):
            raise StructureError("compose root is not a mapping")

        resources: list[_Resource] = []
        for key_node, value_node in root.value:
            section = IacExtractor._scalar(key_node)
            resource_type = COMPOSE_RESOURCE_SECTIONS.get(section) if section else None
            if resource_type is None:
                continue
            if isinstance(value_node, yaml.ScalarNode) and value_node.value == "":
                # ``volumes:`` with no entries is an empty section, not an error.
                continue
            if not isinstance(value_node, yaml.MappingNode):
                raise StructureError(f"compose {section} is not a mapping")
            for entry_key, entry_value in value_node.value:
                name = IacExtractor._scalar(entry_key)
                if not name:
                    raise StructureError(f"compose {section} entry has no literal name")
                image, templated = IacExtractor._image(entry_value) if resource_type == "service" else (None, False)
                resources.append(
                    _Resource(
                        resource_type=resource_type,
                        name=name,
                        # PyYAML marks are zero-based; RFC spans are one-based.
                        line=entry_key.start_mark.line + 1,
                        image=image,
                        templated=templated,
                    )
                )
        # Source order already varies with the file; sorting makes the emitted
        # order a function of identity alone, so two byte-identical manifests in
        # different key order still produce the same ordinals.
        resources.sort(key=lambda item: (item.resource_type, item.name, item.line))
        return resources

    @staticmethod
    def _image(service_node: yaml.Node) -> tuple[str | None, bool]:
        """Return ``(literal image, was_templated)`` for one Compose service."""

        if isinstance(service_node, yaml.ScalarNode) and service_node.value == "":
            # ``web:`` with no body declares the service but nothing about it.
            return None, False
        if not isinstance(service_node, yaml.MappingNode):
            raise StructureError("compose service is not a mapping")
        for key_node, value_node in service_node.value:
            if IacExtractor._scalar(key_node) != "image":
                continue
            if not isinstance(value_node, yaml.ScalarNode):
                raise StructureError("compose service image is not a scalar")
            value = value_node.value
            if _INTERPOLATION.search(value):
                return None, True
            return value or None, False
        return None, False

    @staticmethod
    def _scalar(node: yaml.Node) -> str | None:
        """Return a plain scalar key's text, or ``None`` for any other node.

        A non-scalar key (a YAML sequence or mapping used as a key) has no
        literal name to record, so it is never treated as a resource.
        """

        return node.value if isinstance(node, yaml.ScalarNode) else None
