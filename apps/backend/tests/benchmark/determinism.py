"""Real-extraction determinism through SnapshotStore's canonical graph hash."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction import production_extractors
from app.extraction.dependencies import DEPENDENCY_SET_ARRAY_KEYS, merge_dependency_facts
from app.extraction.pipeline import ExtractionPipeline, ProducedExtraction
from app.intelligence import canonical
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base

from benchmark.loader import LoadedFixture

SCHEMA_VERSION = canonical.SCHEMA_VERSION
_SET_ARRAY_KEYS = frozenset({"decorators", *DEPENDENCY_SET_ARRAY_KEYS})


@dataclass(frozen=True)
class DeterminismResult:
    fixture_id: str
    sealed_hash_a: str
    sealed_hash_b: str
    pure_hash_a: str
    pure_hash_b: str

    @property
    def deterministic(self) -> bool:
        return (
            self.sealed_hash_a == self.sealed_hash_b
            and self.pure_hash_a == self.pure_hash_b
            and self.sealed_hash_a == self.pure_hash_a
            and self.sealed_hash_b == self.pure_hash_b
        )


def _extract(fixture: LoadedFixture) -> tuple[ProducedExtraction, ...]:
    return merge_dependency_facts(
        ExtractionPipeline(
            production_extractors(),
            max_source_bytes=fixture.max_source_bytes,
        ).run(fixture.source_files())
    )


def _evidence(record, produced: ProducedExtraction) -> Evidence:
    return Evidence(
        path=record.path,
        start_line=record.start_line,
        end_line=record.end_line,
        extractor=produced.producer_name,
        extractor_version=produced.producer_version,
        logical_line_count=record.logical_line_count,
        granularity=record.granularity,
    )


def _make_repository(session: Session, owner: User, revision_value: str) -> RepositoryRecord:
    record = RepositoryRecord(
        id=str(uuid4()),
        owner_id=owner.id,
        name=f"bench-{uuid4().hex[:6]}",
        source="upload",
        revision_kind="upload",
        revision_value=revision_value,
        revision_ref=None,
        local_path="/stored/revision",
        status="completed",
        file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def _seal_real_graph(
    session: Session,
    fixture: LoadedFixture,
    runs: tuple[ProducedExtraction, ...],
    *,
    reverse: bool,
) -> str:
    owner = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    repository = _make_repository(session, owner, fixture.revision_value())
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", fixture.revision_value()),
        producer_version_set=list(fixture.producer_version_set),
        config={"max_source_bytes": fixture.max_source_bytes},
    )

    ordered_runs = list(reversed(runs)) if reverse else list(runs)
    nodes = [(produced, node) for produced in ordered_runs for node in produced.result.nodes]
    observations = [
        (produced, observation)
        for produced in ordered_runs
        for observation in produced.result.observations
    ]
    diagnostics = [
        (produced, diagnostic)
        for produced in ordered_runs
        for diagnostic in produced.result.diagnostics
    ]
    if reverse:
        nodes.reverse()
        observations.reverse()
        diagnostics.reverse()

    for produced, node in nodes:
        records = [_evidence(record, produced) for record in node.evidence]
        if reverse:
            records.reverse()
        store.add_node(
            snapshot,
            node_kind=node.node_kind,
            stable_key=node.stable_key,
            name=node.name,
            language=node.language,
            properties=node.properties,
            evidence=records,
            set_array_keys=_node_set_array_keys(node.properties),
        )

    for produced, observation in observations:
        store.add_observation(
            snapshot,
            observed_kind=observation.observed_kind,
            subject_kind=observation.subject_kind,
            subject_key=observation.subject_key,
            referent_text=observation.referent_text,
            ordinal=observation.ordinal,
            evidence=_evidence(observation.evidence, produced),
        )

    for produced, diagnostic in diagnostics:
        store.add_diagnostic(
            snapshot,
            code=diagnostic.code,
            category=diagnostic.category,
            severity=diagnostic.severity,
            message=diagnostic.message,
            producer=produced.producer,
            path=diagnostic.path,
            span=diagnostic.span,
            subject=diagnostic.subject,
            details=diagnostic.details,
        )
    return store.seal(snapshot).canonical_graph_hash


def _node_set_array_keys(properties) -> frozenset[str]:
    return frozenset(key for key in _SET_ARRAY_KEYS if properties and key in properties)


def _normalized_properties(properties):
    if properties is None:
        return None
    return canonical.normalize_declared_arrays(
        dict(properties),
        set_array_keys=_node_set_array_keys(properties),
        context="node properties",
    )


def _evidence_mapping(record, produced: ProducedExtraction) -> dict[str, object]:
    return {
        "path": record.path,
        "start_line": record.start_line,
        "end_line": record.end_line,
        "granularity": record.granularity,
        "extractor": produced.producer_name,
        "extractor_version": produced.producer_version,
    }


def _pure_real_hash(
    fixture: LoadedFixture,
    runs: tuple[ProducedExtraction, ...],
    *,
    reverse: bool,
) -> str:
    nodes_by_key: dict[str, dict[str, object]] = {}
    observations: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    ordered_runs = list(reversed(runs)) if reverse else list(runs)
    for produced in ordered_runs:
        for node in produced.result.nodes:
            evidence = [_evidence_mapping(record, produced) for record in node.evidence]
            record = {
                "node_kind": node.node_kind,
                "stable_key": node.stable_key,
                "truth_class": "observed",
                "name": node.name,
                "language": node.language,
                # Declared set arrays must be sorted here exactly as
                # ``SnapshotStore.add_node`` sorts them, or this independent
                # hash would disagree with the sealed one purely because the
                # extractor emitted set members in source order.
                "properties": _normalized_properties(node.properties),
                "evidence": evidence,
            }
            existing = nodes_by_key.get(node.stable_key)
            if existing is None:
                nodes_by_key[node.stable_key] = record
            else:
                for key in ("node_kind", "truth_class", "name", "language", "properties"):
                    if existing[key] != record[key]:
                        raise AssertionError(
                            f"conflicting real node output for {node.stable_key!r}"
                        )
                existing["evidence"] = [*existing["evidence"], *evidence]

        for observation in produced.result.observations:
            evidence = _evidence_mapping(observation.evidence, produced)
            observation_id = canonical.compute_observation_id(
                revision_kind="upload",
                revision_value=fixture.revision_value(),
                observed_kind=observation.observed_kind,
                subject_kind=observation.subject_kind,
                subject_key=observation.subject_key,
                referent_text=observation.referent_text,
                ordinal=observation.ordinal,
                evidence=evidence,
                schema_version=SCHEMA_VERSION,
            )
            observations.append(
                {
                    "observation_id": observation_id,
                    "observed_kind": observation.observed_kind,
                    "subject_kind": observation.subject_kind,
                    "subject_key": observation.subject_key,
                    "referent_text": observation.referent_text,
                    "ordinal": observation.ordinal,
                    "evidence": evidence,
                }
            )

        for diagnostic in produced.result.diagnostics:
            diagnostics.append(
                {
                    "code": diagnostic.code,
                    "category": diagnostic.category,
                    "severity": diagnostic.severity,
                    "message": diagnostic.message,
                    "producer": produced.producer,
                    "path": diagnostic.path,
                    "span": (
                        {
                            "start_line": diagnostic.span[0],
                            "end_line": diagnostic.span[1],
                        }
                        if diagnostic.span is not None
                        else None
                    ),
                    "subject": diagnostic.subject,
                    "object": None,
                    "details": dict(diagnostic.details) if diagnostic.details else None,
                }
            )

    nodes = list(nodes_by_key.values())
    if reverse:
        nodes.reverse()
        observations.reverse()
        diagnostics.reverse()
        for node in nodes:
            node["evidence"] = list(reversed(node["evidence"]))
    return canonical.compute_canonical_graph_hash(
        revision_kind="upload",
        revision_value=fixture.revision_value(),
        producer_version_set=list(fixture.producer_version_set),
        config_hash=canonical.compute_config_hash(
            {"max_source_bytes": fixture.max_source_bytes}
        ),
        nodes=nodes,
        edges=[],
        assertions=[],
        observations=observations,
        diagnostics=diagnostics,
        schema_version=SCHEMA_VERSION,
    )


def check_fixture(fixture: LoadedFixture, db_path: Path) -> DeterminismResult:
    """Extract twice, vary persistence order, and compare real canonical hashes."""

    runs_a = _extract(fixture)
    runs_b = _extract(fixture)
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        with factory() as session:
            sealed_a = _seal_real_graph(session, fixture, runs_a, reverse=False)
        with factory() as session:
            sealed_b = _seal_real_graph(session, fixture, runs_b, reverse=True)
    finally:
        engine.dispose()
    return DeterminismResult(
        fixture_id=fixture.fixture_id,
        sealed_hash_a=sealed_a,
        sealed_hash_b=sealed_b,
        pure_hash_a=_pure_real_hash(fixture, runs_a, reverse=False),
        pure_hash_b=_pure_real_hash(fixture, runs_b, reverse=True),
    )
