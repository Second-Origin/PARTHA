"""Deterministic merge of dependency facts onto one logical identity (#156, #209).

A dependency is one entity that several files describe. ``package.json`` and
``apps/admin/package.json`` may both *declare* ``react``; ``package-lock.json``
may *resolve* it to an exact version; a nested npm tree may resolve it twice.
Every one of those is a fact about the same ``dep:npm:react`` node.

The extractors cannot merge this themselves — each ``extract()`` call sees one
file — so each emits one ``ExtractedNode`` per fact. Left unmerged, two nodes
sharing a stable key reach :meth:`SnapshotStore.add_node` as two writes whose
``properties`` differ, which it correctly rejects as an internal conflict,
failing analysis for a repository shape that is not an error.

This module folds them into one node per stable key carrying two explicitly
separate collections:

``declarations``
    What a manifest asked for — a range or specifier such as ``^18.3.0``.
``resolutions``
    What a lockfile recorded as installed — an exact pin such as ``18.3.1``.

Keeping them apart is the point. A caret range is not an installed version, and
a lockfile entry is not proof of a direct dependency, so neither collection is
allowed to stand in for the other. Both are declared *set* arrays, so canonical
serialization sorts and de-duplicates them and the graph hash cannot depend on
the order files happened to be read in.

The merged node is emitted once **per contributing producer**, each carrying
only that producer's own evidence records. ``add_node`` creates the node on the
first write and unions evidence on the rest, so a single node ends up with
manifest evidence attributed to ``dependency-manifest`` and lockfile evidence
attributed to ``dependency-lockfile`` — no producer is credited with a span it
did not read.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from app.extraction.base import ExtractedEvidence, ExtractedNode, ExtractionResult
from app.extraction.lockfiles import LockfileExtractor
from app.extraction.manifests import DependencyManifestExtractor
from app.extraction.pipeline import ProducedExtraction

#: Producer names allowed to contribute to one merged dependency node, in the
#: order their records are considered when picking the node's display name. A
#: stable key claimed by any producer outside this set is a genuine identity
#: conflict, not a multi-file description of one dependency.
DEPENDENCY_PRODUCERS: tuple[str, ...] = (
    DependencyManifestExtractor.name,
    LockfileExtractor.name,
)

#: Node ``properties`` keys whose arrays have set semantics (RFC §12.3).
DEPENDENCY_SET_ARRAY_KEYS = frozenset({"declarations", "resolutions"})

_DECLARATION_FIELDS = ("version", "dependency_type", "manifest_path", "workspace_path")
_RESOLUTION_FIELDS = (
    "resolved_version",
    "dependency_scope",
    "lockfile_path",
    "lockfile_format",
    "lockfile_entry",
    "workspace_path",
)


def merge_dependency_facts(produced: tuple[ProducedExtraction, ...]) -> tuple[ProducedExtraction, ...]:
    """Combine per-file dependency nodes sharing a stable key into one record.

    Returns the merged entries first, ahead of every other produced entry: a
    per-file ``dependency``/``resolution`` observation references its node's
    stable key, and ``add_observation`` enforces a same-snapshot foreign key to
    an already-persisted node. Observations stay exactly where they were
    produced; only the now-redundant per-file dependency nodes move.
    """

    groups: dict[str, list[tuple[ProducedExtraction, ExtractedNode]]] = defaultdict(list)
    for item in produced:
        for node in item.result.nodes:
            if node.node_kind == "dependency":
                groups[node.stable_key].append((item, node))
    if not groups:
        return produced

    mergeable = {
        stable_key: members
        for stable_key, members in groups.items()
        if all(item.producer_name in DEPENDENCY_PRODUCERS for item, _ in members)
    }
    if not mergeable:
        return produced

    # {producer identity: [merged node carrying only that producer's evidence]}
    by_producer: dict[tuple[str, str], list[ExtractedNode]] = defaultdict(list)
    for stable_key in sorted(mergeable):
        merged = _merged_node(stable_key, mergeable[stable_key])
        for identity, evidence in _evidence_by_producer(mergeable[stable_key]).items():
            by_producer[identity].append(replace(merged, evidence=evidence))
    merged_entries = [
        ProducedExtraction(producer_name, producer_version, ExtractionResult(nodes=tuple(nodes)))
        for (producer_name, producer_version), nodes in sorted(by_producer.items())
    ]

    rewritten: list[ProducedExtraction] = []
    for item in produced:
        kept = tuple(
            node for node in item.result.nodes if not (node.node_kind == "dependency" and node.stable_key in mergeable)
        )
        rewritten.append(
            item if kept == item.result.nodes else replace(item, result=replace(item.result, nodes=kept))
        )
    return tuple(merged_entries) + tuple(rewritten)


def _member_order(pair: tuple[ProducedExtraction, ExtractedNode]) -> tuple[int, str, int, int]:
    """Order members so the merged record is a function of content, not read order.

    Manifest declarations rank ahead of lockfile resolutions so a declared
    dependency keeps the name its manifest spelled — the name a reader of the
    repository would recognize — while a lockfile-only entry still gets one.
    """

    item, node = pair
    properties = node.properties or {}
    source_path = str(properties.get("manifest_path") or properties.get("lockfile_path") or "")
    rank = DEPENDENCY_PRODUCERS.index(item.producer_name)
    return (rank, source_path, node.evidence[0].start_line, node.evidence[0].end_line)


def _merged_node(stable_key: str, members: list[tuple[ProducedExtraction, ExtractedNode]]) -> ExtractedNode:
    ordered = sorted(members, key=_member_order)
    declarations: list[dict[str, object]] = []
    resolutions: list[dict[str, object]] = []
    for item, node in ordered:
        properties = node.properties or {}
        record: dict[str, object] = {
            "name": node.name,
            "start_line": node.evidence[0].start_line,
            "end_line": node.evidence[0].end_line,
            "extractor": item.producer_name,
            "extractor_version": item.producer_version,
        }
        if item.producer_name == LockfileExtractor.name:
            record.update({field: properties.get(field) for field in _RESOLUTION_FIELDS})
            resolutions.append(record)
        else:
            record.update({field: properties.get(field) for field in _DECLARATION_FIELDS})
            declarations.append(record)
    return ExtractedNode(
        node_kind="dependency",
        stable_key=stable_key,
        name=ordered[0][1].name,
        language=None,
        evidence=(),
        properties={
            "ecosystem": (ordered[0][1].properties or {}).get("ecosystem"),
            # Both keys are always present. An empty ``resolutions`` list states
            # "no supported lockfile pinned this dependency" as a fact, which is
            # the honest answer; omitting the key would make "not resolved" and
            # "not looked at" indistinguishable.
            "declarations": declarations,
            "resolutions": resolutions,
        },
    )


def _evidence_by_producer(
    members: list[tuple[ProducedExtraction, ExtractedNode]],
) -> dict[tuple[str, str], tuple[ExtractedEvidence, ...]]:
    grouped: dict[tuple[str, str], list[ExtractedEvidence]] = defaultdict(list)
    for item, node in sorted(members, key=_member_order):
        grouped[(item.producer_name, item.producer_version)].extend(node.evidence)
    return {identity: tuple(records) for identity, records in grouped.items()}
