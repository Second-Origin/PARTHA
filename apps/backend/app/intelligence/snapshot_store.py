"""Persistence, lifecycle, and sealing for Repository Intelligence snapshots.

This is the persistence boundary for the ``ri.v1`` storage contract (#88,
RFC-0001 §11). It does **not** produce facts: extraction, resolution, and
classification remain the responsibility of producers (#89-#91) behind the
``RepositoryIntelligenceEngine`` boundary. The store accepts already-produced
facts, enforces the RFC invariants, seals the snapshot in one transaction, and
guarantees immutability afterwards.

Responsibilities:

- create ``building`` snapshots keyed on a complete semantic identity (RFC §3.3);
- accept nodes, edges, assertions, observations, evidence, derivation
  references, and diagnostics, computing their deterministic identities;
- reject provenance that violates the contract at write time (absolute paths,
  traversal, invalid spans);
- run pre-seal validation (RFC §11.2), compute the canonical graph hash
  (RFC §12), and flip ``building`` -> ``completed`` atomically;
- reuse an existing completed snapshot for an identical semantic identity, and
  create a distinct snapshot when any identity component changes (RFC §3.4);
- reject every mutation of a completed snapshot at the persistence boundary
  (RFC §11.3), via a ``before_flush`` guard that catches direct ORM writes too.
"""

from __future__ import annotations

import uuid
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import inspect, select
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.intelligence import canonical
from app.models.snapshot import (
    RiAssertion,
    RiDerivation,
    RiDiagnostic,
    RiEdge,
    RiEvidence,
    RiNode,
    RiObservation,
    RiSnapshot,
)
from app.models.repository import RepositoryRecord

SCHEMA_VERSION = canonical.SCHEMA_VERSION

_CHILD_TYPES = (RiNode, RiEdge, RiAssertion, RiObservation, RiEvidence, RiDerivation, RiDiagnostic)
_FATAL_SEVERITY = "fatal"
_GIT_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_UPLOAD_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOWED_TRANSITIONS_KEY = "ri_allowed_snapshot_transitions"
_DIAGNOSTIC_SET_ARRAY_KEYS = frozenset({"candidates"})


class SnapshotError(Exception):
    """Base class for snapshot persistence errors."""


class SnapshotImmutableError(SnapshotError):
    """A completed snapshot (or one of its facts) was modified (RFC §11.3)."""


class SnapshotSealError(SnapshotError):
    """Pre-seal validation failed; the snapshot must not seal (RFC §11.2)."""


class SnapshotStateError(SnapshotError):
    """An operation was attempted against a snapshot in the wrong state."""


class SnapshotAlreadySealedError(SnapshotError):
    """A second snapshot tried to seal for an identity that is already sealed."""

    def __init__(self, message: str, existing: RiSnapshot | None = None) -> None:
        super().__init__(message)
        self.existing = existing


# ---------------------------------------------------------------------------
# Completed-snapshot immutability guard (RFC §11.3)
# ---------------------------------------------------------------------------


def _persisted_state(snapshot: RiSnapshot) -> str | None:
    """Return a snapshot's database-persisted state (before the current flush).

    During the sealing flush the in-memory state is already ``completed`` while
    the persisted value is still ``building``; this reads the persisted value so
    the seal itself is permitted while post-seal writes are rejected.
    """

    history = inspect(snapshot).attrs.state.history
    if history.deleted:
        return history.deleted[0]
    if history.unchanged:
        return history.unchanged[0]
    return None


def _owning_snapshot(session: Session, obj: object) -> RiSnapshot | None:
    snapshot_id = getattr(obj, "snapshot_id", None)
    if snapshot_id is None:
        return None
    key = session.identity_key(RiSnapshot, snapshot_id)
    return session.identity_map.get(key)


def _stored_snapshot_state(session: Session, snapshot_id: str | None) -> str | None:
    if snapshot_id is None:
        return None
    snapshot = session.identity_map.get(session.identity_key(RiSnapshot, snapshot_id))
    if snapshot is not None:
        state = _persisted_state(snapshot)
        if state is not None:
            return state
        if snapshot in session.new:
            return snapshot.state
    return session.connection().execute(
        select(RiSnapshot.state).where(RiSnapshot.snapshot_id == snapshot_id)
    ).scalar_one_or_none()


@event.listens_for(Session, "before_flush")
def _guard_completed_snapshots(session: Session, _flush_context, _instances) -> None:
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, RiSnapshot):
            persisted_state = _persisted_state(obj)
            if persisted_state is None and obj not in session.new:
                persisted_state = session.connection().execute(
                    select(RiSnapshot.state).where(RiSnapshot.snapshot_id == obj.snapshot_id)
                ).scalar_one_or_none()
            if persisted_state == "completed":
                raise SnapshotImmutableError("A completed snapshot is immutable and cannot be modified.")
            if persisted_state is not None and obj.state != persisted_state:
                allowed = session.info.get(_ALLOWED_TRANSITIONS_KEY, set())
                if (obj.snapshot_id, persisted_state, obj.state) not in allowed:
                    raise SnapshotStateError(
                        f"snapshot lifecycle transition {persisted_state!r} -> {obj.state!r} "
                        "must go through SnapshotStore"
                    )
        elif isinstance(obj, _CHILD_TYPES):
            if _stored_snapshot_state(session, getattr(obj, "snapshot_id", None)) == "completed":
                raise SnapshotImmutableError("Facts of a completed snapshot are immutable.")
    for obj in list(session.deleted):
        # Deleting the whole snapshot (retention / repository deletion cascade)
        # is allowed; surgically deleting a fact from a still-present completed
        # snapshot is a mutation and is rejected.
        if isinstance(obj, RiSnapshot) and _persisted_state(obj) == "completed":
            raise SnapshotImmutableError("A completed snapshot cannot be deleted directly.")
        if isinstance(obj, _CHILD_TYPES):
            snapshot = _owning_snapshot(session, obj)
            if (snapshot is None or snapshot not in session.deleted) and _stored_snapshot_state(
                session, getattr(obj, "snapshot_id", None)
            ) == "completed":
                raise SnapshotImmutableError("Facts of a completed snapshot cannot be deleted.")


@event.listens_for(Session, "do_orm_execute")
def _reject_bulk_snapshot_mutation(orm_execute_state) -> None:
    """Bulk ORM writes bypass per-instance history, so reject that route.

    SnapshotStore's instance-based methods are the supported persistence path;
    allowing ``session.execute(update(...))`` would bypass both lifecycle and
    canonical-hash maintenance.
    """

    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    table = getattr(orm_execute_state.statement, "table", None)
    if table is not None and table.name in {
        "ri_snapshots",
        "ri_nodes",
        "ri_edges",
        "ri_assertions",
        "ri_observations",
        "ri_evidence",
        "ri_derivations",
        "ri_diagnostics",
    }:
        raise SnapshotImmutableError("Bulk snapshot mutations are not a supported persistence route.")


# ---------------------------------------------------------------------------
# Input value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Revision:
    kind: str
    value: str
    ref: str | None = None


@dataclass(frozen=True)
class Evidence:
    path: str
    start_line: int
    end_line: int
    extractor: str
    extractor_version: str
    logical_line_count: int
    granularity: str = "span"

    def as_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "granularity": self.granularity,
            "extractor": self.extractor,
            "extractor_version": self.extractor_version,
        }


def observation_ref(observation_id: str) -> dict[str, str]:
    return {"kind": "observation", "observation_id": observation_id}


def node_ref(stable_key: str) -> dict[str, str]:
    return {"kind": "node", "stable_key": stable_key}


def edge_ref(edge_id: str) -> dict[str, str]:
    return {"kind": "edge", "edge_id": edge_id}


def assertion_ref(assertion_id: str) -> dict[str, str]:
    return {"kind": "assertion", "assertion_id": assertion_id}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class SnapshotStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- identity / lifecycle ------------------------------------------------

    def find_completed(
        self,
        *,
        repository_id: str,
        revision_value: str,
        schema_version: str,
        producer_version_set: Sequence[str],
        config_hash: str,
    ) -> RiSnapshot | None:
        statement = select(RiSnapshot).where(
            RiSnapshot.repository_id == repository_id,
            RiSnapshot.revision_value == revision_value,
            RiSnapshot.schema_version == schema_version,
            RiSnapshot.producer_set_hash == canonical.producer_set_hash(producer_version_set),
            RiSnapshot.config_hash == config_hash,
            RiSnapshot.state == "completed",
        )
        return self.db.scalars(statement).first()

    def get_for_owner(self, snapshot_id: str, owner_id: str) -> RiSnapshot | None:
        """Owner-scoped snapshot lookup; cross-owner and missing both return None."""

        statement = (
            select(RiSnapshot)
            .join(RepositoryRecord, RepositoryRecord.id == RiSnapshot.repository_id)
            .where(RiSnapshot.snapshot_id == snapshot_id, RepositoryRecord.owner_id == owner_id)
        )
        return self.db.scalars(statement).first()

    def find_completed_for_owner(
        self,
        *,
        owner_id: str,
        repository_id: str,
        revision_value: str,
        schema_version: str,
        producer_version_set: Sequence[str],
        config_hash: str,
    ) -> RiSnapshot | None:
        statement = (
            select(RiSnapshot)
            .join(RepositoryRecord, RepositoryRecord.id == RiSnapshot.repository_id)
            .where(
                RepositoryRecord.owner_id == owner_id,
                RiSnapshot.repository_id == repository_id,
                RiSnapshot.revision_value == revision_value,
                RiSnapshot.schema_version == schema_version,
                RiSnapshot.producer_set_hash == canonical.producer_set_hash(producer_version_set),
                RiSnapshot.config_hash == config_hash,
                RiSnapshot.state == "completed",
            )
        )
        return self.db.scalars(statement).first()

    def begin(
        self,
        *,
        repository_id: str,
        revision: Revision,
        producer_version_set: Sequence[str],
        schema_version: str = SCHEMA_VERSION,
        config: Mapping[str, object] | None = None,
        config_hash: str | None = None,
        config_set_array_keys: frozenset[str] = frozenset(),
        config_path_keys: frozenset[str] = frozenset(),
    ) -> RiSnapshot:
        """Create a ``building`` snapshot with a fixed semantic identity.

        The complete semantic identity — including the normalized planned
        producer set and ``config_hash`` — is computed here, before any facts are
        written, exactly as required for pre-enqueue idempotency (RFC §3.3).
        """

        self._require_matching_repository(repository_id, revision)

        producers = canonical.normalize_producer_version_set(producer_version_set)
        if any("@" not in producer or producer.startswith("@") or producer.endswith("@") for producer in producers):
            raise SnapshotSealError("producer_version_set entries must use 'producer@version'")
        resolved_config_hash = self._resolve_config_hash(
            config=config,
            config_hash=config_hash,
            set_array_keys=config_set_array_keys,
            path_keys=config_path_keys,
        )
        if not _HASH_RE.fullmatch(resolved_config_hash):
            raise SnapshotSealError("config_hash must be a sha256 content identity")
        snapshot = RiSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex}",
            repository_id=repository_id,
            revision_kind=revision.kind,
            revision_value=revision.value,
            revision_ref=revision.ref,
            schema_version=schema_version,
            producer_version_set=producers,
            producer_set_hash=canonical.producer_set_hash(producers),
            config_hash=resolved_config_hash,
            state="building",
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def get_or_reuse(
        self,
        *,
        repository_id: str,
        revision: Revision,
        producer_version_set: Sequence[str],
        schema_version: str = SCHEMA_VERSION,
        config: Mapping[str, object] | None = None,
        config_hash: str | None = None,
        config_set_array_keys: frozenset[str] = frozenset(),
        config_path_keys: frozenset[str] = frozenset(),
    ) -> tuple[RiSnapshot, bool]:
        """Return ``(snapshot, reused)`` for a semantic identity (RFC §3.4).

        An identical semantic identity reuses the existing completed snapshot; a
        changed revision, schema version, producer set, or config produces a new
        ``building`` snapshot.
        """

        # Validate the supplied revision and confirm it matches the repository
        # *before* searching for a reusable snapshot. ``find_completed`` keys on
        # ``revision_value`` alone, so an unvalidated malformed request (e.g. a
        # ``git`` kind carrying an ``sha256:`` value) could otherwise be answered
        # with an unrelated upload snapshot that merely shares the value.
        self._require_matching_repository(repository_id, revision)
        resolved_config_hash = self._resolve_config_hash(
            config=config,
            config_hash=config_hash,
            set_array_keys=config_set_array_keys,
            path_keys=config_path_keys,
        )
        existing = self.find_completed(
            repository_id=repository_id,
            revision_value=revision.value,
            schema_version=schema_version,
            producer_version_set=producer_version_set,
            config_hash=resolved_config_hash,
        )
        if existing is not None:
            return existing, True
        snapshot = self.begin(
            repository_id=repository_id,
            revision=revision,
            producer_version_set=producer_version_set,
            schema_version=schema_version,
            config_hash=resolved_config_hash,
            config_set_array_keys=config_set_array_keys,
            config_path_keys=config_path_keys,
        )
        return snapshot, False

    def mark_failed(self, snapshot: RiSnapshot, *, code: str | None = None) -> RiSnapshot:
        self._require_building(snapshot)
        snapshot.state = "failed"
        snapshot.failure_code = code
        self._commit_transition(snapshot, from_state="building", to_state="failed")
        return snapshot

    # -- fact writers --------------------------------------------------------

    def add_node(
        self,
        snapshot: RiSnapshot,
        *,
        node_kind: str,
        stable_key: str,
        name: str | None = None,
        language: str | None = None,
        properties: Mapping[str, object] | None = None,
        evidence: Sequence[Evidence] = (),
        truth_class: str = "observed",
        set_array_keys: frozenset[str] = frozenset(),
        ordered_array_keys: frozenset[str] = frozenset(),
    ) -> RiNode:
        self._require_building(snapshot)
        node_kind = canonical.nfc(node_kind)
        stable_key = canonical.normalize_stable_key(node_kind, stable_key)
        normalized_properties = (
            canonical.normalize_declared_arrays(
                dict(properties),
                set_array_keys=set_array_keys,
                ordered_array_keys=ordered_array_keys,
                context="node properties",
            )
            if properties
            else None
        )
        name = canonical.nfc(name) if name is not None else None
        language = canonical.nfc(language) if language is not None else None
        existing = self.db.scalars(
            select(RiNode).where(
                RiNode.snapshot_id == snapshot.snapshot_id,
                RiNode.stable_key == stable_key,
            )
        ).first()
        if existing is not None:
            candidate = (node_kind, name, language, truth_class, normalized_properties)
            stored = (
                existing.node_kind,
                existing.name,
                existing.language,
                existing.truth_class,
                existing.properties,
            )
            if candidate != stored:
                raise SnapshotSealError(f"conflicting node records share stable key {stable_key!r}")
            for record in evidence:
                self._add_evidence(snapshot, record, node_ref=existing.id)
            return existing
        node = RiNode(
            snapshot_id=snapshot.snapshot_id,
            stable_key=stable_key,
            node_kind=node_kind,
            name=name,
            language=language,
            truth_class=truth_class,
            properties=normalized_properties,
        )
        self.db.add(node)
        self.db.flush()
        for record in evidence:
            self._add_evidence(snapshot, record, node_ref=node.id)
        return node

    def add_observation(
        self,
        snapshot: RiSnapshot,
        *,
        observed_kind: str,
        subject_kind: str,
        subject_key: str,
        evidence: Evidence,
        referent_text: str | None = None,
        ordinal: int = 1,
    ) -> RiObservation:
        self._require_building(snapshot)
        observed_kind = canonical.validate_predicate(observed_kind)
        subject_kind = canonical.nfc(subject_kind)
        subject_key = canonical.normalize_stable_key(subject_kind, subject_key)
        referent_text = canonical.nfc(referent_text) if referent_text is not None else None
        observation_id = canonical.compute_observation_id(
            revision_kind=snapshot.revision_kind,
            revision_value=snapshot.revision_value,
            observed_kind=observed_kind,
            subject_kind=subject_kind,
            subject_key=subject_key,
            referent_text=referent_text,
            ordinal=ordinal,
            evidence=evidence.as_mapping(),
            schema_version=snapshot.schema_version,
        )
        existing = self.db.scalars(
            select(RiObservation).where(
                RiObservation.snapshot_id == snapshot.snapshot_id,
                RiObservation.observation_id == observation_id,
            )
        ).first()
        if existing is not None:
            self._add_evidence(snapshot, evidence, observation_ref=existing.id)
            return existing
        observation = RiObservation(
            snapshot_id=snapshot.snapshot_id,
            observation_id=observation_id,
            observed_kind=observed_kind,
            subject_kind=subject_kind,
            subject_key=subject_key,
            referent_text=referent_text,
            ordinal=ordinal,
        )
        self.db.add(observation)
        self.db.flush()
        self._add_evidence(snapshot, evidence, observation_ref=observation.id)
        return observation

    def add_edge(
        self,
        snapshot: RiSnapshot,
        *,
        subject_kind: str,
        subject_key: str,
        predicate: str,
        object_kind: str,
        object_key: str,
        producer: str,
        producer_version: str,
        evidence: Sequence[Evidence] = (),
        derived_from: Sequence[Mapping[str, str]] = (),
        truth_class: str = "resolved",
    ) -> RiEdge:
        self._require_building(snapshot)
        subject_kind = canonical.nfc(subject_kind)
        object_kind = canonical.nfc(object_kind)
        subject_key = canonical.normalize_stable_key(subject_kind, subject_key)
        object_key = canonical.normalize_stable_key(object_kind, object_key)
        predicate = canonical.validate_predicate(predicate)
        producer = canonical.nfc(producer)
        producer_version = canonical.nfc(producer_version)
        edge_id = canonical.compute_edge_id(subject_key, predicate, object_key)
        existing = self.db.scalars(
            select(RiEdge).where(
                RiEdge.snapshot_id == snapshot.snapshot_id,
                RiEdge.edge_id == edge_id,
            )
        ).first()
        if existing is not None:
            candidate = (subject_kind, object_kind, truth_class, producer, producer_version)
            stored = (
                existing.subject_kind,
                existing.object_kind,
                existing.truth_class,
                existing.producer,
                existing.producer_version,
            )
            if candidate != stored:
                raise SnapshotSealError(f"conflicting edge records share identity {edge_id!r}")
            for record in evidence:
                self._add_evidence(snapshot, record, edge_ref=existing.id)
            for reference in derived_from:
                self._add_derivation(snapshot, reference, edge_ref=existing.id)
            return existing
        edge = RiEdge(
            snapshot_id=snapshot.snapshot_id,
            edge_id=edge_id,
            subject_kind=subject_kind,
            subject_key=subject_key,
            predicate=predicate,
            object_kind=object_kind,
            object_key=object_key,
            truth_class=truth_class,
            producer=producer,
            producer_version=producer_version,
        )
        self.db.add(edge)
        self.db.flush()
        for record in evidence:
            self._add_evidence(snapshot, record, edge_ref=edge.id)
        for reference in derived_from:
            self._add_derivation(snapshot, reference, edge_ref=edge.id)
        return edge

    def add_assertion(
        self,
        snapshot: RiSnapshot,
        *,
        subject_kind: str,
        subject_key: str,
        predicate: str,
        value: Mapping[str, object],
        producer: str,
        producer_version: str,
        derived_from: Sequence[Mapping[str, str]] = (),
        truth_class: str = "inferred",
        set_array_keys: frozenset[str] = frozenset(),
        ordered_array_keys: frozenset[str] = frozenset(),
    ) -> RiAssertion:
        self._require_building(snapshot)
        subject_kind = canonical.nfc(subject_kind)
        subject_key = canonical.normalize_stable_key(subject_kind, subject_key)
        predicate = canonical.validate_predicate(predicate)
        normalized_value = canonical.normalize_declared_arrays(
            dict(value),
            set_array_keys=set_array_keys,
            ordered_array_keys=ordered_array_keys,
            context="assertion value",
        )
        producer = canonical.nfc(producer)
        producer_version = canonical.nfc(producer_version)
        assertion_id = canonical.compute_assertion_id(
            subject_kind=subject_kind,
            subject_key=subject_key,
            predicate=predicate,
            value=normalized_value,
            truth_class=truth_class,
            producer=producer,
            producer_version=producer_version,
            derived_from=list(derived_from),
            schema_version=snapshot.schema_version,
        )
        existing = self.db.scalars(
            select(RiAssertion).where(
                RiAssertion.snapshot_id == snapshot.snapshot_id,
                RiAssertion.assertion_id == assertion_id,
            )
        ).first()
        if existing is not None:
            return existing
        assertion = RiAssertion(
            snapshot_id=snapshot.snapshot_id,
            assertion_id=assertion_id,
            subject_kind=subject_kind,
            subject_key=subject_key,
            predicate=predicate,
            value=normalized_value,
            truth_class=truth_class,
            producer=producer,
            producer_version=producer_version,
        )
        self.db.add(assertion)
        self.db.flush()
        for reference in derived_from:
            self._add_derivation(snapshot, reference, assertion_ref=assertion.id)
        return assertion

    def add_diagnostic(
        self,
        snapshot: RiSnapshot,
        *,
        code: str,
        category: str,
        severity: str,
        message: str,
        producer: str,
        path: str | None = None,
        span: tuple[int, int] | None = None,
        subject: str | None = None,
        object: str | None = None,  # noqa: A002 - mirrors RFC field name
        details: Mapping[str, object] | None = None,
        set_array_keys: frozenset[str] = frozenset(),
        ordered_array_keys: frozenset[str] = frozenset(),
    ) -> RiDiagnostic:
        self._require_building(snapshot)
        normalized_path = canonical.normalize_repo_path(path) if path is not None else None
        if span is not None and not (1 <= span[0] <= span[1]):
            raise SnapshotSealError("diagnostic spans must be one-based and inclusive")
        normalized_details = (
            canonical.normalize_declared_arrays(
                dict(details),
                set_array_keys=_DIAGNOSTIC_SET_ARRAY_KEYS | set_array_keys,
                ordered_array_keys=ordered_array_keys,
                context="diagnostic details",
            )
            if details
            else None
        )
        diagnostic = RiDiagnostic(
            snapshot_id=snapshot.snapshot_id,
            code=canonical.nfc(code),
            category=canonical.nfc(category),
            severity=canonical.nfc(severity),
            message=canonical.nfc(message),
            producer=canonical.nfc(producer),
            path=normalized_path,
            span_start_line=span[0] if span else None,
            span_end_line=span[1] if span else None,
            subject_key=canonical.nfc(subject) if subject is not None else None,
            object_key=canonical.nfc(object) if object is not None else None,
            details=normalized_details,
        )
        self.db.add(diagnostic)
        self.db.flush()
        return diagnostic

    # -- sealing -------------------------------------------------------------

    def seal(self, snapshot: RiSnapshot) -> RiSnapshot:
        """Validate, hash, and complete a snapshot in one transaction (RFC §11.2)."""

        self._require_building(snapshot)
        # Load under no_autoflush so a post-insert mutation that violates a stored
        # invariant is caught by _validate (and turned into a clean ``failed``
        # transition) instead of tripping a database constraint mid-flush.
        with self.db.no_autoflush:
            facts = self._load_facts(snapshot)
        try:
            self._validate(snapshot, facts)
            graph_hash = self._compute_hash(snapshot, facts)
            # Reproducibility check (RFC §11.2 rule 10): recomputation is stable.
            if graph_hash != self._compute_hash(snapshot, facts):
                raise SnapshotSealError("canonical graph hash is not reproducible")
        except SnapshotSealError:
            self._fail_seal(snapshot)
            raise
        except (canonical.CanonicalizationError, canonical.PathEscapeError) as exc:
            # A canonicalization or path failure at seal time means the stored
            # graph cannot be reduced to a valid canonical form. The build must
            # transition to ``failed`` rather than remain stuck in ``building``.
            self._fail_seal(snapshot)
            raise SnapshotSealError(f"snapshot could not be canonicalized during seal: {exc}") from exc

        snapshot.canonical_graph_hash = graph_hash
        snapshot.actual_producers = self._observed_producers(facts)
        snapshot.state = "completed"
        snapshot.sealed_at = datetime.now(UTC)
        identity = {
            "repository_id": snapshot.repository_id,
            "revision_value": snapshot.revision_value,
            "schema_version": snapshot.schema_version,
            "producer_version_set": list(snapshot.producer_version_set),
            "config_hash": snapshot.config_hash,
        }
        try:
            self._commit_transition(snapshot, from_state="building", to_state="completed")
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.find_completed(**identity)
            raise SnapshotAlreadySealedError(
                "A completed snapshot already exists for this semantic identity.",
                existing=existing,
            ) from exc
        return snapshot

    # -- internals -----------------------------------------------------------

    def _fail_seal(self, snapshot: RiSnapshot) -> None:
        """Transition a rejected build to ``failed`` and commit it (RFC §11.2)."""

        self._discard_tampered_facts()
        snapshot.state = "failed"
        snapshot.failure_code = snapshot.failure_code or "RI-INT-VALIDATION"
        self._commit_transition(snapshot, from_state="building", to_state="failed")

    def _discard_tampered_facts(self) -> None:
        """Revert in-memory edits to stored facts so the fail commit can proceed.

        A post-insert mutation that :meth:`_validate` rejected (an over-long span,
        an unnormalized path) is still pending in the session; expiring the dirty
        fact rows restores their persisted values so the ``failed`` transition is
        not itself blocked by the invalid edit or its database constraint.
        """

        for obj in list(self.db.dirty):
            if isinstance(obj, _CHILD_TYPES):
                self.db.expire(obj)

    def _require_building(self, snapshot: RiSnapshot) -> None:
        if snapshot.state != "building":
            raise SnapshotStateError(f"snapshot {snapshot.snapshot_id} is not building (state={snapshot.state})")

    def _commit_transition(self, snapshot: RiSnapshot, *, from_state: str, to_state: str) -> None:
        transition = (snapshot.snapshot_id, from_state, to_state)
        allowed = self.db.info.setdefault(_ALLOWED_TRANSITIONS_KEY, set())
        allowed.add(transition)
        try:
            self.db.commit()
        finally:
            allowed.discard(transition)
            if not allowed:
                self.db.info.pop(_ALLOWED_TRANSITIONS_KEY, None)

    def _require_matching_repository(self, repository_id: str, revision: Revision) -> RepositoryRecord:
        """Validate ``revision`` and confirm it is this repository's revision.

        The moving ``revision.ref`` is never part of semantic identity, so only
        ``(kind, value)`` is compared against the repository's immutable revision
        columns (RFC §3.3).
        """

        self._validate_revision(revision)
        repository = self.db.get(RepositoryRecord, repository_id)
        if repository is None:
            raise SnapshotSealError("snapshot repository does not exist")
        if (repository.revision_kind, repository.revision_value) != (revision.kind, revision.value):
            raise SnapshotSealError("snapshot revision does not match its repository revision")
        return repository

    @staticmethod
    def _validate_revision(revision: Revision) -> None:
        if revision.kind == "git":
            if not _GIT_REVISION_RE.fullmatch(revision.value):
                raise SnapshotSealError("git revisions require a 40-character lowercase commit SHA")
            if revision.ref is not None and not revision.ref.startswith("refs/"):
                raise SnapshotSealError("git revision refs must be normalized under refs/")
            return
        if revision.kind == "upload":
            if not _UPLOAD_REVISION_RE.fullmatch(revision.value) or revision.ref is not None:
                raise SnapshotSealError("upload revisions require sha256 content identity and a null ref")
            return
        raise SnapshotSealError("revision kind must be 'git' or 'upload'")

    @staticmethod
    def _resolve_config_hash(
        *,
        config: Mapping[str, object] | None,
        config_hash: str | None,
        set_array_keys: frozenset[str],
        path_keys: frozenset[str],
    ) -> str:
        computed = canonical.compute_config_hash(
            config,
            set_array_keys=set_array_keys,
            path_keys=path_keys,
        )
        if config_hash is not None and config is not None and config_hash != computed:
            raise SnapshotSealError("provided config_hash does not match canonical configuration")
        return config_hash or computed

    def _add_evidence(
        self,
        snapshot: RiSnapshot,
        record: Evidence,
        *,
        node_ref: int | None = None,
        edge_ref: int | None = None,
        observation_ref: int | None = None,
    ) -> RiEvidence:
        # Reject absolute paths / traversal (RFC §4.2, §13) and invalid spans
        # (RFC §6.2) at write time. Normalization raises PathEscapeError.
        normalized_path = canonical.normalize_repo_path(record.path)
        extractor = canonical.nfc(record.extractor)
        extractor_version = canonical.nfc(record.extractor_version)
        if not normalized_path:
            raise SnapshotSealError("evidence path must identify a repository-relative file")
        if record.granularity not in {"span", "file"}:
            raise SnapshotSealError("evidence granularity must be 'span' or 'file'")
        if not extractor or not extractor_version:
            raise SnapshotSealError("evidence extractor and extractor_version are required")
        if not (1 <= record.start_line <= record.end_line <= record.logical_line_count):
            raise SnapshotSealError(
                f"invalid evidence span {record.start_line}..{record.end_line} "
                f"for {normalized_path!r} with {record.logical_line_count} logical lines"
            )
        parent_column = (
            RiEvidence.node_ref
            if node_ref is not None
            else RiEvidence.edge_ref
            if edge_ref is not None
            else RiEvidence.observation_ref
        )
        parent_value = node_ref if node_ref is not None else edge_ref if edge_ref is not None else observation_ref
        existing = self.db.scalars(
            select(RiEvidence).where(
                RiEvidence.snapshot_id == snapshot.snapshot_id,
                parent_column == parent_value,
                RiEvidence.path == normalized_path,
                RiEvidence.start_line == record.start_line,
                RiEvidence.end_line == record.end_line,
                RiEvidence.granularity == record.granularity,
                RiEvidence.extractor == extractor,
                RiEvidence.extractor_version == extractor_version,
            )
        ).first()
        if existing is not None:
            # The same evidence identity must carry the same logical-line count;
            # a producer that reports a different file length for an identical
            # span is internally inconsistent and must not be silently merged.
            if existing.logical_line_count != record.logical_line_count:
                raise SnapshotSealError(
                    f"conflicting logical_line_count for duplicate evidence on {normalized_path!r}: "
                    f"{existing.logical_line_count} != {record.logical_line_count}"
                )
            return existing
        evidence = RiEvidence(
            snapshot_id=snapshot.snapshot_id,
            node_ref=node_ref,
            edge_ref=edge_ref,
            observation_ref=observation_ref,
            path=normalized_path,
            start_line=record.start_line,
            end_line=record.end_line,
            logical_line_count=record.logical_line_count,
            granularity=record.granularity,
            extractor=extractor,
            extractor_version=extractor_version,
        )
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def _add_derivation(
        self,
        snapshot: RiSnapshot,
        reference: Mapping[str, str],
        *,
        edge_ref: int | None = None,
        assertion_ref: int | None = None,
    ) -> RiDerivation:
        kind = reference.get("kind")
        if kind not in canonical._REFERENCE_IDENTITY_FIELD:
            raise SnapshotSealError("derived_from contains an unsupported reference kind")
        identity_field = canonical._REFERENCE_IDENTITY_FIELD[kind]
        expected_keys = {"kind", identity_field}
        if set(reference) != expected_keys or not reference.get(identity_field):
            raise SnapshotSealError("derived_from reference does not match the RFC tagged shape")
        identity = canonical.nfc(reference[identity_field])
        parent_column = RiDerivation.edge_ref if edge_ref is not None else RiDerivation.assertion_ref
        parent_value = edge_ref if edge_ref is not None else assertion_ref
        existing = self.db.scalars(
            select(RiDerivation).where(
                RiDerivation.snapshot_id == snapshot.snapshot_id,
                parent_column == parent_value,
                RiDerivation.ref_kind == kind,
                RiDerivation.ref_identity == identity,
            )
        ).first()
        if existing is not None:
            return existing
        derivation = RiDerivation(
            snapshot_id=snapshot.snapshot_id,
            edge_ref=edge_ref,
            assertion_ref=assertion_ref,
            ref_kind=kind,
            ref_identity=identity,
        )
        self.db.add(derivation)
        self.db.flush()
        return derivation

    def _load_facts(self, snapshot: RiSnapshot) -> "_Facts":
        snapshot_id = snapshot.snapshot_id
        nodes = list(self.db.scalars(select(RiNode).where(RiNode.snapshot_id == snapshot_id)))
        edges = list(self.db.scalars(select(RiEdge).where(RiEdge.snapshot_id == snapshot_id)))
        assertions = list(self.db.scalars(select(RiAssertion).where(RiAssertion.snapshot_id == snapshot_id)))
        observations = list(self.db.scalars(select(RiObservation).where(RiObservation.snapshot_id == snapshot_id)))
        evidence = list(self.db.scalars(select(RiEvidence).where(RiEvidence.snapshot_id == snapshot_id)))
        derivations = list(self.db.scalars(select(RiDerivation).where(RiDerivation.snapshot_id == snapshot_id)))
        diagnostics = list(self.db.scalars(select(RiDiagnostic).where(RiDiagnostic.snapshot_id == snapshot_id)))
        return _Facts(nodes, edges, assertions, observations, evidence, derivations, diagnostics)

    def _validate(self, snapshot: RiSnapshot, facts: "_Facts") -> None:
        producer_set = set(snapshot.producer_version_set)
        normalized_producers = canonical.normalize_producer_version_set(snapshot.producer_version_set)
        if snapshot.producer_version_set != normalized_producers:
            raise SnapshotSealError("producer_version_set is not normalized")
        if snapshot.producer_set_hash != canonical.producer_set_hash(normalized_producers):
            raise SnapshotSealError("producer_set_hash does not match producer_version_set")
        if not _HASH_RE.fullmatch(snapshot.config_hash):
            raise SnapshotSealError("config_hash is not a canonical sha256 identity")
        self._validate_revision(Revision(snapshot.revision_kind, snapshot.revision_value, snapshot.revision_ref))

        # Rule 3 / §8.4: a fatal diagnostic fails the snapshot.
        if any(diagnostic.severity == _FATAL_SEVERITY for diagnostic in facts.diagnostics):
            snapshot.failure_code = "RI-FATAL-DIAGNOSTIC"
            raise SnapshotSealError("snapshot has a fatal diagnostic and cannot seal")

        # Rule 5: exactly one repo:root node.
        repo_nodes = [node for node in facts.nodes if node.node_kind == "repository"]
        if len(repo_nodes) != 1 or repo_nodes[0].stable_key != "repo:root":
            raise SnapshotSealError("a completed snapshot must contain exactly one repo:root node")

        node_keys = {node.stable_key for node in facts.nodes}
        node_kind_by_key: dict[str, str] = {}
        for node in facts.nodes:
            try:
                normalized_key = canonical.normalize_stable_key(node.node_kind, node.stable_key)
            except (canonical.CanonicalizationError, canonical.PathEscapeError) as exc:
                raise SnapshotSealError(f"invalid stable key {node.stable_key!r}") from exc
            if normalized_key != node.stable_key:
                raise SnapshotSealError(f"stable key {node.stable_key!r} is not normalized")
            normalized_properties = canonical.normalize_content(node.properties or {})
            if node.properties is not None and normalized_properties != node.properties:
                raise SnapshotSealError("node properties are not canonically normalized")
            node_kind_by_key[node.stable_key] = node.node_kind
        evidence_by_node = defaultdict(list)
        evidence_by_edge = defaultdict(list)
        evidence_by_observation = defaultdict(list)
        for record in facts.evidence:
            if record.node_ref is not None:
                evidence_by_node[record.node_ref].append(record)
            elif record.edge_ref is not None:
                evidence_by_edge[record.edge_ref].append(record)
            elif record.observation_ref is not None:
                evidence_by_observation[record.observation_ref].append(record)
            # Re-check every stored evidence record against the contract, so a
            # post-insert mutation cannot smuggle an invalid span, an unnormalized
            # or escaping path, or an undeclared producer into a sealed snapshot
            # (RFC §6, §11.2, §13).
            self._validate_stored_evidence(record, producer_set)

        # Rule 1: every observed node has >=1 valid evidence record.
        for node in facts.nodes:
            if node.truth_class == "observed" and not evidence_by_node.get(node.id):
                raise SnapshotSealError(f"observed node {node.stable_key!r} has no evidence")

        # Every observation has exactly one evidence record (RFC §6.4).
        for observation in facts.observations:
            if len(evidence_by_observation.get(observation.id, [])) != 1:
                raise SnapshotSealError(f"observation {observation.observation_id} must have exactly one evidence record")
            if node_kind_by_key.get(observation.subject_key) != observation.subject_kind:
                raise SnapshotSealError(f"observation {observation.observation_id} has an invalid subject")
            evidence = evidence_by_observation[observation.id][0]
            recomputed = canonical.compute_observation_id(
                revision_kind=snapshot.revision_kind,
                revision_value=snapshot.revision_value,
                observed_kind=observation.observed_kind,
                subject_kind=observation.subject_kind,
                subject_key=observation.subject_key,
                referent_text=observation.referent_text,
                ordinal=observation.ordinal,
                evidence=self._evidence_dict(evidence),
                schema_version=snapshot.schema_version,
            )
            if recomputed != observation.observation_id:
                raise SnapshotSealError(f"observation {observation.observation_id} identity does not recompute")

        derivations_by_edge = defaultdict(list)
        derivations_by_assertion = defaultdict(list)
        for derivation in facts.derivations:
            if derivation.edge_ref is not None:
                derivations_by_edge[derivation.edge_ref].append(derivation)
            elif derivation.assertion_ref is not None:
                derivations_by_assertion[derivation.assertion_ref].append(derivation)

        edge_ids = {edge.edge_id for edge in facts.edges}
        assertion_ids = {assertion.assertion_id for assertion in facts.assertions}
        observation_ids = {observation.observation_id for observation in facts.observations}

        # Rule 2: edge endpoints resolve to nodes in this snapshot (also a DB FK).
        for edge in facts.edges:
            if (
                node_kind_by_key.get(edge.subject_key) != edge.subject_kind
                or node_kind_by_key.get(edge.object_key) != edge.object_kind
            ):
                raise SnapshotSealError(f"edge {edge.edge_id} references a node outside the snapshot")
            if canonical.compute_edge_id(edge.subject_key, edge.predicate, edge.object_key) != edge.edge_id:
                raise SnapshotSealError(f"edge {edge.edge_id} identity does not recompute")
            if not evidence_by_edge.get(edge.id):
                raise SnapshotSealError(f"resolved edge {edge.edge_id} has no evidence")
            edge_derivations = derivations_by_edge.get(edge.id, [])
            if not edge_derivations or not any(item.ref_kind == "observation" for item in edge_derivations):
                raise SnapshotSealError(f"resolved edge {edge.edge_id} must derive from a source observation")
            self._require_producer(edge.producer, edge.producer_version, producer_set)

        # Assertion subjects resolve; assertion identity recomputes (rule 8).
        for assertion in facts.assertions:
            if node_kind_by_key.get(assertion.subject_key) != assertion.subject_kind:
                raise SnapshotSealError(f"assertion {assertion.assertion_id} references a node outside the snapshot")
            references = self._derivation_refs(derivations_by_assertion.get(assertion.id, []))
            if not references:
                raise SnapshotSealError(f"inferred assertion {assertion.assertion_id} has no derivation")
            recomputed = canonical.compute_assertion_id(
                subject_kind=assertion.subject_kind,
                subject_key=assertion.subject_key,
                predicate=assertion.predicate,
                value=assertion.value,
                truth_class=assertion.truth_class,
                producer=assertion.producer,
                producer_version=assertion.producer_version,
                derived_from=references,
                schema_version=snapshot.schema_version,
            )
            if recomputed != assertion.assertion_id:
                raise SnapshotSealError(f"assertion {assertion.assertion_id} identity does not recompute")
            normalized_value = canonical.normalize_content(assertion.value)
            if normalized_value != assertion.value:
                raise SnapshotSealError("assertion value is not canonically normalized")
            self._require_producer(assertion.producer, assertion.producer_version, producer_set)

        # Rule 7: every derivation reference resolves in the snapshot, and the
        # derivation graph is acyclic.
        self._validate_derivation_graph(
            facts,
            node_keys=node_keys,
            edge_ids=edge_ids,
            assertion_ids=assertion_ids,
            observation_ids=observation_ids,
            derivations_by_edge=derivations_by_edge,
            derivations_by_assertion=derivations_by_assertion,
        )

        # Diagnostic producers must be declared too (RFC §11.2 rule 6).
        for diagnostic in facts.diagnostics:
            if diagnostic.producer not in producer_set:
                raise SnapshotSealError(f"diagnostic producer {diagnostic.producer!r} is not in the producer set")
            if (diagnostic.span_start_line is None) != (diagnostic.span_end_line is None):
                raise SnapshotSealError("diagnostic span endpoints must either both be present or both be null")
            normalized_details = canonical.normalize_content(diagnostic.details or {})
            if diagnostic.details is not None and normalized_details != diagnostic.details:
                raise SnapshotSealError("diagnostic details are not canonically normalized")

    def _validate_stored_evidence(self, record: RiEvidence, producer_set: set[str]) -> None:
        """Revalidate one persisted evidence record before sealing (RFC §6, §11.2).

        Every check that :meth:`_add_evidence` runs at write time is re-asserted
        against the stored row, so a direct mutation after insertion cannot leave
        an invalid record in a completed snapshot. Path canonicalization failures
        surface as :class:`SnapshotSealError` so the build fails rather than
        remaining stuck in ``building``.
        """

        if not record.extractor or not record.extractor_version:
            raise SnapshotSealError("stored evidence extractor and extractor_version must be non-empty")
        if record.granularity not in {"span", "file"}:
            raise SnapshotSealError(f"stored evidence has invalid granularity {record.granularity!r}")
        try:
            normalized_path = canonical.normalize_repo_path(record.path)
        except canonical.PathEscapeError as exc:
            raise SnapshotSealError(
                f"stored evidence path {record.path!r} is absolute or escapes the repository root"
            ) from exc
        if not normalized_path:
            raise SnapshotSealError("stored evidence path must identify a repository-relative file")
        if normalized_path != record.path:
            raise SnapshotSealError(f"stored evidence path {record.path!r} is not in normalized form")
        if record.logical_line_count is None or record.logical_line_count < 1:
            raise SnapshotSealError("stored evidence logical_line_count must be >= 1")
        if not (1 <= record.start_line <= record.end_line <= record.logical_line_count):
            raise SnapshotSealError(
                f"stored evidence span {record.start_line}..{record.end_line} is not bounded by "
                f"{record.logical_line_count} logical lines for {record.path!r}"
            )
        # Provenance extractor must be a declared producer (RFC §11.2 rule 6).
        self._require_producer(record.extractor, record.extractor_version, producer_set)

    def _require_producer(self, producer: str, version: str, producer_set: set[str]) -> None:
        identifier = f"{producer}@{version}"
        if identifier not in producer_set:
            raise SnapshotSealError(f"producer {identifier!r} is not declared in producer_version_set")

    def _derivation_refs(self, derivations: Sequence[RiDerivation]) -> list[dict[str, str]]:
        references: list[dict[str, str]] = []
        for derivation in derivations:
            field_name = canonical._REFERENCE_IDENTITY_FIELD[derivation.ref_kind]
            references.append({"kind": derivation.ref_kind, field_name: derivation.ref_identity})
        return references

    def _validate_derivation_graph(
        self,
        facts: "_Facts",
        *,
        node_keys: set[str],
        edge_ids: set[str],
        assertion_ids: set[str],
        observation_ids: set[str],
        derivations_by_edge: Mapping[int, Sequence[RiDerivation]],
        derivations_by_assertion: Mapping[int, Sequence[RiDerivation]],
    ) -> None:
        # Build an adjacency map keyed by fact identity for derived facts only.
        outgoing: dict[str, list[str]] = {}
        edge_id_by_row = {edge.id: edge.edge_id for edge in facts.edges}
        assertion_id_by_row = {assertion.id: assertion.assertion_id for assertion in facts.assertions}

        def resolve(reference: RiDerivation) -> str:
            kind, identity = reference.ref_kind, reference.ref_identity
            table = {
                "observation": observation_ids,
                "node": node_keys,
                "edge": edge_ids,
                "assertion": assertion_ids,
            }[kind]
            if identity not in table:
                raise SnapshotSealError(f"derived_from reference {kind}:{identity} does not resolve in the snapshot")
            return f"{kind}:{identity}"

        for row_id, derivations in derivations_by_edge.items():
            key = f"edge:{edge_id_by_row[row_id]}"
            outgoing[key] = [resolve(derivation) for derivation in derivations]
        for row_id, derivations in derivations_by_assertion.items():
            key = f"assertion:{assertion_id_by_row[row_id]}"
            outgoing[key] = [resolve(derivation) for derivation in derivations]

        # Cycle detection over the derivation graph.
        WHITE, GREY, BLACK = 0, 1, 2
        color: dict[str, int] = defaultdict(int)

        def visit(node: str) -> None:
            color[node] = GREY
            for target in outgoing.get(node, ()):
                if color[target] == GREY:
                    raise SnapshotSealError("derivation graph contains a cycle")
                if color[target] == WHITE and target in outgoing:
                    visit(target)
            color[node] = BLACK

        for node in list(outgoing):
            if color[node] == WHITE:
                visit(node)

    def _observed_producers(self, facts: "_Facts") -> list[str]:
        producers: set[str] = set()
        for record in facts.evidence:
            producers.add(f"{record.extractor}@{record.extractor_version}")
        for edge in facts.edges:
            producers.add(f"{edge.producer}@{edge.producer_version}")
        for assertion in facts.assertions:
            producers.add(f"{assertion.producer}@{assertion.producer_version}")
        for diagnostic in facts.diagnostics:
            producers.add(diagnostic.producer)
        return sorted(producers)

    def _compute_hash(self, snapshot: RiSnapshot, facts: "_Facts") -> str:
        evidence_by_node = defaultdict(list)
        evidence_by_edge = defaultdict(list)
        evidence_by_observation: dict[int, RiEvidence] = {}
        for record in facts.evidence:
            if record.node_ref is not None:
                evidence_by_node[record.node_ref].append(self._evidence_dict(record))
            elif record.edge_ref is not None:
                evidence_by_edge[record.edge_ref].append(self._evidence_dict(record))
            elif record.observation_ref is not None:
                evidence_by_observation[record.observation_ref] = self._evidence_dict(record)

        derivations_by_edge = defaultdict(list)
        derivations_by_assertion = defaultdict(list)
        for derivation in facts.derivations:
            reference = {
                "kind": derivation.ref_kind,
                canonical._REFERENCE_IDENTITY_FIELD[derivation.ref_kind]: derivation.ref_identity,
            }
            if derivation.edge_ref is not None:
                derivations_by_edge[derivation.edge_ref].append(reference)
            elif derivation.assertion_ref is not None:
                derivations_by_assertion[derivation.assertion_ref].append(reference)

        nodes = [
            {
                "node_kind": node.node_kind,
                "stable_key": node.stable_key,
                "truth_class": node.truth_class,
                "name": node.name,
                "language": node.language,
                "properties": node.properties,
                "evidence": evidence_by_node.get(node.id, []),
            }
            for node in facts.nodes
        ]
        edges = [
            {
                "edge_id": edge.edge_id,
                "subject_kind": edge.subject_kind,
                "subject_key": edge.subject_key,
                "predicate": edge.predicate,
                "object_kind": edge.object_kind,
                "object_key": edge.object_key,
                "truth_class": edge.truth_class,
                "producer": edge.producer,
                "producer_version": edge.producer_version,
                "evidence": evidence_by_edge.get(edge.id, []),
                "derived_from": derivations_by_edge.get(edge.id, []),
            }
            for edge in facts.edges
        ]
        assertions = [
            {
                "assertion_id": assertion.assertion_id,
                "subject_kind": assertion.subject_kind,
                "subject_key": assertion.subject_key,
                "predicate": assertion.predicate,
                "value": assertion.value,
                "truth_class": assertion.truth_class,
                "producer": assertion.producer,
                "producer_version": assertion.producer_version,
                "derived_from": derivations_by_assertion.get(assertion.id, []),
            }
            for assertion in facts.assertions
        ]
        observations = [
            {
                "observation_id": observation.observation_id,
                "observed_kind": observation.observed_kind,
                "subject_kind": observation.subject_kind,
                "subject_key": observation.subject_key,
                "referent_text": observation.referent_text,
                "ordinal": observation.ordinal,
                "evidence": evidence_by_observation[observation.id],
            }
            for observation in facts.observations
        ]
        diagnostics = [
            {
                "code": diagnostic.code,
                "category": diagnostic.category,
                "severity": diagnostic.severity,
                "message": diagnostic.message,
                "producer": diagnostic.producer,
                "path": diagnostic.path,
                "span": {"start_line": diagnostic.span_start_line, "end_line": diagnostic.span_end_line}
                if diagnostic.span_start_line is not None
                else None,
                "subject": diagnostic.subject_key,
                "object": diagnostic.object_key,
                "details": diagnostic.details,
            }
            for diagnostic in facts.diagnostics
        ]
        return canonical.compute_canonical_graph_hash(
            revision_kind=snapshot.revision_kind,
            revision_value=snapshot.revision_value,
            producer_version_set=snapshot.producer_version_set,
            config_hash=snapshot.config_hash,
            nodes=nodes,
            edges=edges,
            assertions=assertions,
            observations=observations,
            diagnostics=diagnostics,
            schema_version=snapshot.schema_version,
        )

    @staticmethod
    def _evidence_dict(record: RiEvidence) -> dict[str, object]:
        return {
            "path": record.path,
            "start_line": record.start_line,
            "end_line": record.end_line,
            "granularity": record.granularity,
            "extractor": record.extractor,
            "extractor_version": record.extractor_version,
        }


@dataclass
class _Facts:
    nodes: list[RiNode]
    edges: list[RiEdge]
    assertions: list[RiAssertion]
    observations: list[RiObservation]
    evidence: list[RiEvidence]
    derivations: list[RiDerivation]
    diagnostics: list[RiDiagnostic]
