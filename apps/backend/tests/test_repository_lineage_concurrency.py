"""Real-PostgreSQL concurrency and integrity coverage for #299 (RFC-0002).

Per the migration plan's own §13/§14: "SQLite tests prove migration
portability, constraint reflection, and serialized-writer behavior. They
cannot prove PostgreSQL row-lock behavior, transaction isolation,
partial-index semantics, or concurrent create reconciliation." Every test in
this file runs against a real, separate-connection PostgreSQL database using
threading.Barrier synchronization -- not thread timing or sleeps -- matching
the existing `test_concurrent_refresh_on_postgres_mints_one_successor`
pattern in test_auth_concurrency.py. This whole file skips without
PARTHA_TEST_PG_URL.
"""

import os
import threading
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

PG_URL = os.environ.get("PARTHA_TEST_PG_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="set PARTHA_TEST_PG_URL to run the Postgres lineage concurrency tests"
)


def _make_session_factory():
    from app.models.base import Base

    engine = create_engine(PG_URL)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _make_user(session, email: str | None = None) -> str:
    from app.models.user import User

    user = User(id=str(uuid.uuid4()), email=email or f"lineage-{uuid.uuid4().hex}@example.com")
    session.add(user)
    session.commit()
    return user.id


def _repository_record(owner_id: str, revision_value: str, **overrides) -> "RepositoryRecord":  # noqa: F821
    from app.models.repository import RepositoryRecord

    base = dict(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name="widgets",
        source="github",
        source_url="https://github.com/acme/widgets",
        branch="main",
        revision_kind="git",
        revision_value=revision_value,
        revision_ref="refs/heads/main",
        local_path="/tmp/x",
        status="analysing",
    )
    base.update(overrides)
    return RepositoryRecord(**base)


def test_concurrent_imports_into_an_existing_lineage_get_unique_consecutive_sequences():
    """Two different commits, same canonical pair, an already-existing
    lineage: both must serialize on the atomic counter update and receive
    distinct, consecutive sequences -- never the same one."""
    from app.repositories.repository_repository import RepositoryRepository

    engine, Session = _make_session_factory()
    setup = Session()
    try:
        owner_id = _make_user(setup)
    finally:
        setup.close()

    results: list[int] = []
    errors: list[BaseException] = []
    results_lock = threading.Lock()
    start = threading.Barrier(2)

    def worker(revision_value: str) -> None:
        session = Session()
        try:
            start.wait(timeout=10)
            persisted = RepositoryRepository(session).add_with_lineage(
                _repository_record(owner_id, revision_value),
                owner_id=owner_id,
                canonical_source_key="github.com/acme/widgets",
                canonical_branch="refs/heads/main",
                display_name="widgets",
            )
            with results_lock:
                results.append(persisted.sequence)
        except BaseException as exc:  # noqa: BLE001 -- captured for the assertion below, not swallowed
            with results_lock:
                errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(sha,)) for sha in ("a" * 40, "b" * 40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    try:
        assert not [t for t in threads if t.is_alive()], "a worker thread did not finish within the timeout"
        assert not errors, errors
        assert sorted(results) == [1, 2], results

        verify = Session()
        try:
            from app.models.repository_lineage import RepositoryLineage

            lineage = verify.scalars(select(RepositoryLineage).where(RepositoryLineage.owner_id == owner_id)).one()
            assert lineage.next_sequence == 3
        finally:
            verify.close()
    finally:
        _cleanup_owner(Session, owner_id)
        engine.dispose()


def test_two_first_imports_racing_create_exactly_one_lineage():
    """No lineage exists yet for this canonical pair; two callers race to
    create it. The canonical partial unique index must let exactly one win;
    the loser reloads the winner's lineage and retries, ending with one
    lineage and two distinct sequences -- never two lineages."""
    from app.repositories.repository_repository import RepositoryRepository

    engine, Session = _make_session_factory()
    setup = Session()
    try:
        owner_id = _make_user(setup)
    finally:
        setup.close()

    results: list[int] = []
    errors: list[BaseException] = []
    results_lock = threading.Lock()
    start = threading.Barrier(2)

    def worker(revision_value: str) -> None:
        session = Session()
        try:
            start.wait(timeout=10)
            persisted = RepositoryRepository(session).add_with_lineage(
                _repository_record(owner_id, revision_value),
                owner_id=owner_id,
                canonical_source_key="github.com/acme/first-race",
                canonical_branch="refs/heads/main",
                display_name="first-race",
            )
            with results_lock:
                results.append(persisted.sequence)
        except BaseException as exc:  # noqa: BLE001
            with results_lock:
                errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(sha,)) for sha in ("c" * 40, "d" * 40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    try:
        assert not [t for t in threads if t.is_alive()], "a worker thread did not finish within the timeout"
        assert not errors, errors
        assert sorted(results) == [1, 2], results

        verify = Session()
        try:
            from app.models.repository_lineage import RepositoryLineage

            lineages = verify.scalars(
                select(RepositoryLineage).where(
                    RepositoryLineage.owner_id == owner_id,
                    RepositoryLineage.canonical_source_key == "github.com/acme/first-race",
                )
            ).all()
            assert len(lineages) == 1, f"expected exactly one lineage, found {len(lineages)}"
        finally:
            verify.close()
    finally:
        _cleanup_owner(Session, owner_id)
        engine.dispose()


def test_two_identical_commits_racing_produce_one_repository_and_one_conflict():
    """The exact same commit imported twice, concurrently: the loser must
    observe the duplicate after serialization and be rejected -- never a
    second repository row, and never a wasted/skipped sequence number."""
    from app.repositories.repository_repository import LineageDuplicateRevision, RepositoryRepository

    engine, Session = _make_session_factory()
    setup = Session()
    try:
        owner_id = _make_user(setup)
    finally:
        setup.close()

    outcomes: list[str] = []
    outcomes_lock = threading.Lock()
    start = threading.Barrier(2)
    shared_commit = "e" * 40

    def worker() -> None:
        session = Session()
        outcome = "error"
        try:
            start.wait(timeout=10)
            RepositoryRepository(session).add_with_lineage(
                _repository_record(owner_id, shared_commit, id=str(uuid.uuid4())),
                owner_id=owner_id,
                canonical_source_key="github.com/acme/identical-race",
                canonical_branch="refs/heads/main",
                display_name="identical-race",
            )
            outcome = "ok"
        except LineageDuplicateRevision:
            outcome = "rejected"
        finally:
            session.close()
            with outcomes_lock:
                outcomes.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    try:
        assert not [t for t in threads if t.is_alive()], "a worker thread did not finish within the timeout"
        assert sorted(outcomes) == ["ok", "rejected"], outcomes

        verify = Session()
        try:
            from app.models.repository import RepositoryRecord
            from app.models.repository_lineage import RepositoryLineage

            repos = verify.scalars(
                select(RepositoryRecord).where(
                    RepositoryRecord.owner_id == owner_id, RepositoryRecord.revision_value == shared_commit
                )
            ).all()
            assert len(repos) == 1, "exactly one repository row must exist for the winning commit"
            lineage = verify.scalars(
                select(RepositoryLineage).where(
                    RepositoryLineage.owner_id == owner_id,
                    RepositoryLineage.canonical_source_key == "github.com/acme/identical-race",
                )
            ).one()
            assert lineage.next_sequence == 2, "the rejected duplicate must not have burned a sequence number"
        finally:
            verify.close()
    finally:
        _cleanup_owner(Session, owner_id)
        engine.dispose()


def test_forced_duplicate_lineage_sequence_pair_is_rejected():
    """Direct proof of the `uq_repositories_lineage_sequence` constraint on
    real Postgres, bypassing the allocator entirely."""
    from app.models.repository_lineage import RepositoryLineage

    engine, Session = _make_session_factory()
    session = Session()
    owner_id = None
    try:
        owner_id = _make_user(session)
        lineage = RepositoryLineage(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            canonical_source_key="github.com/acme/forced-dup",
            canonical_branch="refs/heads/main",
            display_name="forced-dup",
            latest_repository_id=None,
            next_sequence=2,
            created_at=datetime.now(UTC),
        )
        session.add(lineage)
        session.add(_repository_record(owner_id, "f" * 40, lineage_id=lineage.id, sequence=1))
        session.commit()

        session.add(_repository_record(owner_id, "1" * 40, lineage_id=lineage.id, sequence=1))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()
        if owner_id:
            _cleanup_owner(Session, owner_id)
        engine.dispose()


def test_cross_owner_composite_membership_is_rejected_on_real_postgres():
    """Direct proof of `fk_repositories_lineage_owner` on real Postgres: a
    repository can never attach to a lineage owned by a different user, even
    with a forced direct write that bypasses the service layer."""
    from app.models.repository_lineage import RepositoryLineage

    engine, Session = _make_session_factory()
    session = Session()
    owner_id = None
    other_owner_id = None
    try:
        owner_id = _make_user(session)
        other_owner_id = _make_user(session)
        lineage = RepositoryLineage(
            id=str(uuid.uuid4()),
            owner_id=other_owner_id,
            canonical_source_key="github.com/acme/cross-owner",
            canonical_branch="refs/heads/main",
            display_name="cross-owner",
            latest_repository_id=None,
            next_sequence=1,
            created_at=datetime.now(UTC),
        )
        session.add(lineage)
        session.commit()

        session.add(_repository_record(owner_id, "2" * 40, lineage_id=lineage.id, sequence=1))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()
        for cleanup_owner in (owner_id, other_owner_id):
            if cleanup_owner:
                _cleanup_owner(Session, cleanup_owner)
        engine.dispose()


def test_cross_lineage_latest_pointer_is_rejected_on_real_postgres():
    """Direct proof of `fk_repository_lineages_latest_member` on real
    Postgres: a lineage's latest pointer can never name a repository that
    actually belongs to a different lineage."""
    from app.models.repository_lineage import RepositoryLineage

    engine, Session = _make_session_factory()
    session = Session()
    owner_id = None
    try:
        owner_id = _make_user(session)
        lineage_a = RepositoryLineage(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            canonical_source_key="github.com/acme/lineage-a",
            canonical_branch="refs/heads/main",
            display_name="lineage-a",
            latest_repository_id=None,
            next_sequence=2,
            created_at=datetime.now(UTC),
        )
        lineage_b = RepositoryLineage(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            canonical_source_key="github.com/acme/lineage-b",
            canonical_branch="refs/heads/main",
            display_name="lineage-b",
            latest_repository_id=None,
            next_sequence=2,
            created_at=datetime.now(UTC),
        )
        session.add_all([lineage_a, lineage_b])
        record_in_b = _repository_record(owner_id, "3" * 40, lineage_id=lineage_b.id, sequence=1)
        session.add(record_in_b)
        session.commit()

        # Point lineage_a's latest at a repository that actually belongs to
        # lineage_b -- must be rejected.
        lineage_a.latest_repository_id = record_in_b.id
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()
        if owner_id:
            _cleanup_owner(Session, owner_id)
        engine.dispose()


def test_account_deletion_cascades_lineages_for_that_owner_only():
    from app.models.repository_lineage import RepositoryLineage
    from app.models.user import User

    engine, Session = _make_session_factory()
    session = Session()
    owner_id = None
    other_owner_id = None
    try:
        owner_id = _make_user(session)
        other_owner_id = _make_user(session)
        session.add(
            RepositoryLineage(
                id=str(uuid.uuid4()),
                owner_id=owner_id,
                canonical_source_key="github.com/acme/deleted-owner",
                canonical_branch="refs/heads/main",
                display_name="deleted-owner",
                latest_repository_id=None,
                next_sequence=1,
                created_at=datetime.now(UTC),
            )
        )
        other_lineage_id = str(uuid.uuid4())
        session.add(
            RepositoryLineage(
                id=other_lineage_id,
                owner_id=other_owner_id,
                canonical_source_key="github.com/acme/surviving-owner",
                canonical_branch="refs/heads/main",
                display_name="surviving-owner",
                latest_repository_id=None,
                next_sequence=1,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()

        session.delete(session.get(User, owner_id))
        session.commit()

        remaining = session.scalars(select(RepositoryLineage.id)).all()
        assert other_lineage_id in remaining
        assert not any(
            True for _ in session.scalars(select(RepositoryLineage).where(RepositoryLineage.owner_id == owner_id))
        )
    finally:
        session.close()
        if other_owner_id:
            _cleanup_owner(Session, other_owner_id)
        engine.dispose()


def _cleanup_owner(Session, owner_id: str) -> None:
    from app.models.repository import RepositoryRecord
    from app.models.repository_lineage import RepositoryLineage
    from app.models.user import User

    cleanup = Session()
    try:
        cleanup.query(RepositoryRecord).filter(RepositoryRecord.owner_id == owner_id).delete()
        cleanup.query(RepositoryLineage).filter(RepositoryLineage.owner_id == owner_id).delete()
        cleanup.query(User).filter(User.id == owner_id).delete()
        cleanup.commit()
    finally:
        cleanup.close()
