"""Canonical serialization, deterministic identities, and the graph hash.

This module implements the deterministic parts of the Repository Intelligence
v1 contract (RFC-0001) that #88 depends on:

- canonical UTF-8 JSON with RFC 8785 (JCS) semantics — sorted keys, no
  insignificant whitespace, no trailing newline, integers only (RFC §12.1);
- Unicode NFC normalization of every string (RFC §12.4);
- repository-relative POSIX path normalization with traversal/absolute
  rejection (RFC §4.2);
- deterministic content identities for edges, observations, and assertions
  (RFC §5.3, §6.4, §5.6);
- the ``config_hash`` procedure (RFC §12.7);
- the canonical graph hash over five totally-ordered arrays (RFC §12.2, §12.3).

The functions here are pure: they operate on plain mappings, not ORM rows, so
they are independently testable and reusable by later extraction/resolution work
(#89-#95) without importing the persistence layer.

``json.dumps(sort_keys=True)`` is deliberately *not* used on its own. Every
value first passes through :func:`_normalize`, which NFC-normalizes strings,
rejects floats (no float ever appears in hashed content), and rejects
unsupported types, so the byte output satisfies the RFC canonicalization rules
for the integer/string/bool/null/array/object subset this contract uses. The
published RFC digests in §12.7, §5.3, §6.4, and §5.6 are reproduced exactly by
these functions (see ``tests/test_canonical_hash.py``).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "ri.v1"
_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# ASCII unit separator. It cannot appear in a stable key or predicate, so it is
# a safe field separator for the edge-id pre-image (RFC §5.3).
_UNIT_SEPARATOR = "\x1f"

# Tagged derived_from reference ranking (RFC §12.3).
_REFERENCE_RANK = {"observation": 0, "node": 1, "edge": 2, "assertion": 3}
_REFERENCE_IDENTITY_FIELD = {
    "observation": "observation_id",
    "node": "stable_key",
    "edge": "edge_id",
    "assertion": "assertion_id",
}


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized (e.g. a float appears)."""


class PathEscapeError(ValueError):
    """Raised when a path is absolute or escapes the repository root (RFC §4.2)."""


def nfc(value: str) -> str:
    """Return the Unicode NFC normalization of ``value``."""

    return unicodedata.normalize("NFC", value)


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return nfc(value)
    # bool must be checked before int (bool is an int subclass).
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if not (-(2**53) + 1 <= value <= (2**53) - 1):
            raise CanonicalizationError("integers outside the exact JSON/IEEE-754 range are not permitted")
        return value
    if value is None:
        return None
    if isinstance(value, float):
        raise CanonicalizationError("floats are not permitted in canonical content")
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = nfc(str(key))
            if normalized_key in normalized:
                raise CanonicalizationError(f"object keys collide after Unicode normalization: {normalized_key!r}")
            normalized[normalized_key] = _normalize(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    raise CanonicalizationError(f"unsupported type in canonical content: {type(value)!r}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize ``value`` to canonical JCS bytes (RFC §12.1)."""

    normalized = _normalize(value)

    def serialize(node: Any) -> str:
        if node is None:
            return "null"
        if node is True:
            return "true"
        if node is False:
            return "false"
        if isinstance(node, int):
            return str(node)
        if isinstance(node, str):
            # Python's compact JSON string escaping matches JCS for valid
            # Unicode strings. ``ensure_ascii=False`` keeps non-ASCII code
            # points unescaped, as RFC 8785 requires.
            return json.dumps(node, ensure_ascii=False, separators=(",", ":"))
        if isinstance(node, list):
            return "[" + ",".join(serialize(item) for item in node) + "]"
        if isinstance(node, dict):
            # JCS sorts property names as arrays of UTF-16 code units, not by
            # Python's Unicode code-point ordering. The distinction matters for
            # supplementary-plane characters versus high BMP code points.
            keys = sorted(node, key=lambda key: key.encode("utf-16be"))
            return "{" + ",".join(f"{serialize(key)}:{serialize(node[key])}" for key in keys) + "}"
        raise CanonicalizationError(f"unsupported normalized type: {type(node)!r}")

    try:
        return serialize(normalized).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalizationError("canonical content contains an invalid Unicode surrogate") from exc


def normalize_content(value: Any) -> Any:
    """Return the recursively NFC-normalized, canonical JSON value."""

    return _normalize(value)


def normalize_declared_arrays(
    value: Any,
    *,
    set_array_keys: frozenset[str] = frozenset(),
    ordered_array_keys: frozenset[str] = frozenset(),
    context: str = "content",
) -> Any:
    """Normalize JSON while enforcing explicit array semantics (RFC §12.3)."""

    overlap = set_array_keys & ordered_array_keys
    if overlap:
        raise CanonicalizationError(f"array keys cannot be both set and ordered: {sorted(overlap)!r}")

    def prepare(node: Any, key: str | None = None) -> Any:
        if isinstance(node, Mapping):
            prepared: dict[str, Any] = {}
            for raw_key, nested in node.items():
                normalized_key = nfc(str(raw_key))
                if normalized_key in prepared:
                    raise CanonicalizationError(
                        f"{context} keys collide after Unicode normalization: {normalized_key!r}"
                    )
                prepared[normalized_key] = prepare(nested, normalized_key)
            return prepared
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            if key not in set_array_keys and key not in ordered_array_keys:
                raise CanonicalizationError(f"{context} array {key!r} has no declared set/order semantics")
            elements = [prepare(item) for item in node]
            if key in set_array_keys:
                by_bytes = {canonical_json_bytes(element): element for element in elements}
                return [by_bytes[encoded] for encoded in sorted(by_bytes)]
            return elements
        return _normalize(node)

    return prepare(value)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_prefixed(data: bytes) -> str:
    """Return ``sha256:<lowercase-hex>`` for ``data``."""

    return f"sha256:{sha256_hex(data)}"


# ---------------------------------------------------------------------------
# Path normalization (RFC §4.2)
# ---------------------------------------------------------------------------


def normalize_repo_path(raw: str) -> str:
    """Normalize a path to a repository-relative POSIX path (RFC §4.2).

    The repository root itself normalizes to the empty string. Absolute paths
    (POSIX ``/...`` or a Windows drive prefix) and paths that lexically escape
    the root (a leading ``..`` that cannot be popped) raise
    :class:`PathEscapeError` — they never produce a node or evidence record and
    are surfaced as ``RI-SEC-PATH-ESCAPE`` diagnostics by callers.
    """

    if raw is None:  # defensive: callers must pass a string
        raise PathEscapeError("path is required")
    text = nfc(str(raw))
    # Windows drive-letter absolute path, e.g. C:\Users -> reject before we
    # fold backslashes into separators.
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        raise PathEscapeError("absolute path is not repository-relative")
    text = text.replace("\\", "/")
    if text.startswith("/"):
        raise PathEscapeError("absolute path is not repository-relative")

    resolved: list[str] = []
    for segment in text.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not resolved:
                raise PathEscapeError("path escapes the repository root")
            resolved.pop()
            continue
        resolved.append(segment)
    return "/".join(resolved)


def is_valid_repo_path(raw: str) -> bool:
    try:
        normalize_repo_path(raw)
    except PathEscapeError:
        return False
    return True


def normalize_stable_key(node_kind: str, stable_key: str) -> str:
    """Validate and normalize the stable-key forms registered by RFC §4.3.

    Unknown future node kinds remain forward-compatible, but their kind and key
    must still be non-empty normalized strings. Registered path-bearing keys are
    normalized exactly, so an unnormalized or escaping spelling cannot enter a
    snapshot.
    """

    kind = nfc(node_kind)
    key = nfc(stable_key)
    if not _TOKEN_RE.fullmatch(kind) or not key:
        raise CanonicalizationError("node kind and stable key must be non-empty canonical tokens")
    if _UNIT_SEPARATOR in key or any(ord(character) < 0x20 for character in key):
        raise CanonicalizationError("stable keys cannot contain control characters")
    if kind == "repository":
        if key != "repo:root":
            raise CanonicalizationError("the repository stable key must be 'repo:root'")
        return key
    if kind == "module":
        if not key.startswith("mod:"):
            raise CanonicalizationError("module stable keys must start with 'mod:'")
        return "mod:" + normalize_repo_path(key[4:])
    if kind == "file":
        if not key.startswith("file:"):
            raise CanonicalizationError("file stable keys must start with 'file:'")
        path = normalize_repo_path(key[5:])
        if not path:
            raise CanonicalizationError("file stable keys require a repository-relative path")
        return "file:" + path
    if kind == "symbol":
        if "::" not in key:
            raise CanonicalizationError("symbol stable keys require '<path>::<qualified-name>'")
        path, qualified_name = key.split("::", 1)
        normalized_path = normalize_repo_path(path)
        if not normalized_path or not qualified_name:
            raise CanonicalizationError("symbol stable keys require a path and qualified name")
        return f"{normalized_path}::{qualified_name}"
    if kind == "dependency":
        if not key.startswith("dep:") or key.count(":") < 2:
            raise CanonicalizationError("dependency stable keys require 'dep:<ecosystem>:<name>'")
        return key
    if kind == "service":
        # An outbound service is identified by its absolute origin. Registering
        # the form here (rather than letting it fall through as an unknown kind)
        # is what stops a relative path or a bare host from entering a snapshot
        # as if it were a proven destination.
        if not key.startswith("svc:") or "://" not in key[4:]:
            raise CanonicalizationError("service stable keys require 'svc:<scheme>://<host>[:<port>]'")
        return key
    if kind == "iac_resource":
        if not key.startswith("iac:") or "::" not in key[4:]:
            raise CanonicalizationError("iac_resource stable keys require 'iac:<manifest-path>::<type>/<name>'")
        path, qualified = key[4:].split("::", 1)
        normalized_path = normalize_repo_path(path)
        if not normalized_path or "/" not in qualified:
            raise CanonicalizationError("iac_resource stable keys require a manifest path and '<type>/<name>'")
        return f"iac:{normalized_path}::{qualified}"
    return key


def validate_predicate(predicate: str) -> str:
    normalized = nfc(predicate)
    if not _TOKEN_RE.fullmatch(normalized):
        raise CanonicalizationError("predicates must be lowercase snake_case tokens")
    return normalized


# ---------------------------------------------------------------------------
# Deterministic identities (RFC §5.3, §6.4, §5.6)
# ---------------------------------------------------------------------------


def compute_edge_id(subject_key: str, predicate: str, object_key: str) -> str:
    """``edge:sha256:<hex>`` over the canonical relationship triple (RFC §5.3)."""

    pre_image = _UNIT_SEPARATOR.join((nfc(subject_key), nfc(predicate), nfc(object_key)))
    return "edge:" + sha256_prefixed(pre_image.encode("utf-8"))


def _identity_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    # The observation identity document uses the five minimum evidence fields
    # WITHOUT granularity (RFC §6.4 identity document), distinct from the
    # granularity-materialized form used when hashing a stored record.
    return {
        "extractor": evidence["extractor"],
        "extractor_version": evidence["extractor_version"],
        "path": normalize_repo_path(evidence["path"]),
        "start_line": evidence["start_line"],
        "end_line": evidence["end_line"],
    }


def compute_observation_id(
    *,
    revision_kind: str,
    revision_value: str,
    observed_kind: str,
    subject_kind: str,
    subject_key: str,
    referent_text: str | None,
    ordinal: int,
    evidence: Mapping[str, Any],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    """``obs:sha256:<hex>`` over the observation identity document (RFC §6.4)."""

    document = {
        "evidence": _identity_evidence(evidence),
        "observed_kind": observed_kind,
        "ordinal": ordinal,
        "referent_text": referent_text,
        "revision": {"kind": revision_kind, "value": revision_value},
        "schema_version": schema_version,
        "subject": {"kind": subject_kind, "stable_key": subject_key},
    }
    return "obs:" + sha256_prefixed(canonical_json_bytes(document))


def _reference_identity(reference: Mapping[str, Any]) -> str:
    kind = reference["kind"]
    return str(reference[_REFERENCE_IDENTITY_FIELD[kind]])


def sort_derived_from(references: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Sort and de-duplicate a tagged ``derived_from`` list (RFC §12.3).

    Ordering is ``(kind_rank, referenced_identity, complete_record_jcs)`` and
    byte-identical references collapse.
    """

    seen: set[bytes] = set()
    unique: list[tuple[dict[str, Any], bytes]] = []
    for reference in references:
        record = _normalize(reference)
        kind = record.get("kind")
        if kind not in _REFERENCE_IDENTITY_FIELD:
            raise CanonicalizationError("derived_from contains an unsupported reference kind")
        identity_field = _REFERENCE_IDENTITY_FIELD[kind]
        if set(record) != {"kind", identity_field} or not record.get(identity_field):
            raise CanonicalizationError("derived_from reference does not match the RFC tagged shape")
        encoded = canonical_json_bytes(record)
        if encoded in seen:
            continue
        seen.add(encoded)
        unique.append((record, encoded))
    unique.sort(key=lambda item: (_REFERENCE_RANK[item[0]["kind"]], _reference_identity(item[0]), item[1]))
    return [record for record, _ in unique]


def compute_assertion_id(
    *,
    subject_kind: str,
    subject_key: str,
    predicate: str,
    value: Mapping[str, Any],
    truth_class: str,
    producer: str,
    producer_version: str,
    derived_from: Sequence[Mapping[str, Any]],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    """``assertion:sha256:<hex>`` over the assertion identity document (RFC §5.6)."""

    document = {
        "derived_from": sort_derived_from(derived_from),
        "predicate": predicate,
        "producer": producer,
        "producer_version": producer_version,
        "schema_version": schema_version,
        "subject": {"kind": subject_kind, "stable_key": subject_key},
        "truth_class": truth_class,
        "value": value,
    }
    return "assertion:" + sha256_prefixed(canonical_json_bytes(document))


# ---------------------------------------------------------------------------
# config_hash (RFC §12.7)
# ---------------------------------------------------------------------------


def compute_config_hash(
    config: Mapping[str, Any] | None,
    *,
    set_array_keys: frozenset[str] = frozenset(),
    path_keys: frozenset[str] = frozenset(),
) -> str:
    """Compute ``config_hash`` for the output-affecting configuration (RFC §12.7).

    Arrays preserve order by default. Callers must explicitly declare keys whose
    semantics are sets; those arrays are sorted and byte-deduplicated. This is
    RFC §12.7's conservative "when in doubt, order-significant" rule.
    """

    if not config:
        return sha256_prefixed(b"{}")

    def prepare(node: Any, key: str | None) -> Any:
        if isinstance(node, Mapping):
            prepared: dict[str, Any] = {}
            for raw_key, value in node.items():
                normalized_key = nfc(str(raw_key))
                if normalized_key in prepared:
                    raise CanonicalizationError(f"config keys collide after Unicode normalization: {normalized_key!r}")
                prepared[normalized_key] = prepare(value, normalized_key)
            return prepared
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            elements = [prepare(item, key) for item in node]
            if key in set_array_keys:
                by_bytes = {canonical_json_bytes(element): element for element in elements}
                elements = [by_bytes[encoded] for encoded in sorted(by_bytes)]
            return elements
        if isinstance(node, str) and key in path_keys:
            return normalize_repo_path(node)
        return node

    prepared = prepare(dict(config), None)
    return sha256_prefixed(canonical_json_bytes(prepared))


# ---------------------------------------------------------------------------
# Producer version set (RFC §3.3, §12.3)
# ---------------------------------------------------------------------------


def normalize_producer_version_set(producers: Sequence[str]) -> list[str]:
    """Lexicographically sort and de-duplicate ``producer@version`` identifiers."""

    return sorted({nfc(str(producer)) for producer in producers}, key=lambda value: value.encode("utf-8"))


def producer_set_hash(producers: Sequence[str]) -> str:
    """Deterministic hash of the normalized producer set for identity indexing."""

    normalized = normalize_producer_version_set(producers)
    return sha256_prefixed(canonical_json_bytes(normalized))


# ---------------------------------------------------------------------------
# Canonical record builders + total ordering (RFC §12.2, §12.3)
# ---------------------------------------------------------------------------


def canonical_evidence_record(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one evidence record, materializing the default granularity."""

    return {
        "path": normalize_repo_path(evidence["path"]),
        "start_line": evidence["start_line"],
        "end_line": evidence["end_line"],
        "granularity": evidence.get("granularity") or "span",
        "extractor": evidence["extractor"],
        "extractor_version": evidence["extractor_version"],
    }


def _order_records(records: Sequence[Mapping[str, Any]], key) -> list[dict[str, Any]]:
    normalized: list[tuple[dict[str, Any], bytes]] = []
    seen: set[bytes] = set()
    for record in records:
        prepared = _normalize(record)
        encoded = canonical_json_bytes(prepared)
        if encoded in seen:
            continue
        seen.add(encoded)
        normalized.append((prepared, encoded))
    normalized.sort(key=lambda item: (*key(item[0]), item[1]))
    return [record for record, _ in normalized]


def order_evidence(evidence_records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    prepared = [canonical_evidence_record(record) for record in evidence_records]
    return _order_records(
        prepared,
        lambda record: (
            record["path"],
            record["start_line"],
            record["end_line"],
            record["granularity"],
            record["extractor"],
            record["extractor_version"],
        ),
    )


def canonical_node_record(node: Mapping[str, Any], *, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    record: dict[str, Any] = {
        "kind": "node",
        "node_kind": node["node_kind"],
        "stable_key": node["stable_key"],
        "truth_class": node["truth_class"],
        "schema_version": schema_version,
        "evidence": order_evidence(node.get("evidence", [])),
    }
    if node.get("name") is not None:
        record["name"] = node["name"]
    if node.get("language") is not None:
        record["language"] = node["language"]
    if node.get("properties"):
        record["properties"] = node["properties"]
    return record


def canonical_edge_record(edge: Mapping[str, Any], *, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    return {
        "kind": "edge",
        "edge_id": edge["edge_id"],
        "subject": {"kind": edge["subject_kind"], "stable_key": edge["subject_key"]},
        "predicate": edge["predicate"],
        "object": {"kind": edge["object_kind"], "stable_key": edge["object_key"]},
        "truth_class": edge["truth_class"],
        "producer": edge["producer"],
        "producer_version": edge["producer_version"],
        "evidence": order_evidence(edge.get("evidence", [])),
        "derived_from": sort_derived_from(edge.get("derived_from", [])),
        "schema_version": schema_version,
    }


def canonical_assertion_record(assertion: Mapping[str, Any], *, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    return {
        "kind": "assertion",
        "assertion_id": assertion["assertion_id"],
        "subject": {"kind": assertion["subject_kind"], "stable_key": assertion["subject_key"]},
        "predicate": assertion["predicate"],
        "value": assertion["value"],
        "truth_class": assertion["truth_class"],
        "producer": assertion["producer"],
        "producer_version": assertion["producer_version"],
        "derived_from": sort_derived_from(assertion.get("derived_from", [])),
        "schema_version": schema_version,
    }


def canonical_observation_record(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": observation["observation_id"],
        "observed_kind": observation["observed_kind"],
        "subject": {"kind": observation["subject_kind"], "stable_key": observation["subject_key"]},
        "referent_text": observation.get("referent_text"),
        "ordinal": observation["ordinal"],
        "evidence": canonical_evidence_record(observation["evidence"]),
    }


def canonical_diagnostic_record(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    span = diagnostic.get("span")
    path = diagnostic.get("path")
    return {
        "code": diagnostic["code"],
        "category": diagnostic["category"],
        "severity": diagnostic["severity"],
        "message": diagnostic["message"],
        "producer": diagnostic["producer"],
        "path": normalize_repo_path(path) if path is not None else None,
        "span": {"start_line": span["start_line"], "end_line": span["end_line"]} if span else None,
        "subject": diagnostic.get("subject"),
        "object": diagnostic.get("object"),
        "details": diagnostic.get("details") or {},
    }


def _consolidate_edges(
    edges: Sequence[Mapping[str, Any]], *, schema_version: str = SCHEMA_VERSION
) -> list[dict[str, Any]]:
    """Collapse duplicate ``(subject, predicate, object)`` triples (RFC §12.3).

    Evidence and ``derived_from`` are set-unioned; every other field must agree
    or the graph is internally inconsistent.
    """

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        record = canonical_edge_record(edge, schema_version=schema_version)
        triple = (
            record["subject"]["stable_key"],
            record["predicate"],
            record["object"]["stable_key"],
        )
        if triple not in grouped:
            grouped[triple] = record
            continue
        existing = grouped[triple]
        for field in ("edge_id", "truth_class", "producer", "producer_version"):
            if existing[field] != record[field]:
                raise CanonicalizationError(f"inconsistent edge field {field!r} for duplicate triple {triple}")
        existing["evidence"] = order_evidence(existing["evidence"] + record["evidence"])
        existing["derived_from"] = sort_derived_from(existing["derived_from"] + record["derived_from"])
    return list(grouped.values())


def compute_canonical_graph_hash(
    *,
    revision_kind: str,
    revision_value: str,
    producer_version_set: Sequence[str],
    config_hash: str,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    assertions: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    diagnostics: Sequence[Mapping[str, Any]],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    """Compute the primary canonical graph hash (RFC §12).

    The result is ``sha256:<hex>`` over the canonical document with five totally
    ordered arrays plus scalar inputs. Insertion order of any array cannot alter
    the result: every array is normalized, de-duplicated, and sorted by a
    semantic tuple with the complete JCS record bytes as the final tie-breaker.
    Volatile fields (database ids, timestamps, ``actual_producers``, the moving
    ``revision.ref``) are excluded because they never enter these records.
    """

    node_records = _order_records(
        [canonical_node_record(node, schema_version=schema_version) for node in nodes],
        lambda record: (record["stable_key"],),
    )
    edge_records = _order_records(
        _consolidate_edges(edges, schema_version=schema_version),
        lambda record: (record["subject"]["stable_key"], record["predicate"], record["object"]["stable_key"]),
    )
    assertion_records = _order_records(
        [canonical_assertion_record(assertion, schema_version=schema_version) for assertion in assertions],
        lambda record: (record["subject"]["stable_key"], record["predicate"], record["assertion_id"]),
    )
    observation_records = _order_records(
        [canonical_observation_record(observation) for observation in observations],
        lambda record: (record["observation_id"],),
    )
    diagnostic_records = _order_records(
        [canonical_diagnostic_record(diagnostic) for diagnostic in diagnostics],
        lambda record: (
            record["code"],
            record["category"],
            record["severity"],
            record["path"] or "",
            (record["span"] or {}).get("start_line", 0),
            (record["span"] or {}).get("end_line", 0),
            record["producer"],
            record["subject"] or "",
            record["object"] or "",
            record["message"],
            canonical_json_bytes(record["details"]).decode("utf-8"),
        ),
    )

    document = {
        "schema_version": schema_version,
        "revision": {"kind": revision_kind, "value": revision_value},
        "producer_version_set": normalize_producer_version_set(producer_version_set),
        "config_hash": config_hash,
        "nodes": node_records,
        "edges": edge_records,
        "assertions": assertion_records,
        "observations": observation_records,
        "diagnostics": diagnostic_records,
    }
    return sha256_prefixed(canonical_json_bytes(document))
