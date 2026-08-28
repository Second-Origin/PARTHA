"""add repository_lineages, expand repositories, and backfill (1 of 2)

Revision ID: 0013_lineage_expand
Revises: 0012_waitlist_entries
Create Date: 2026-08-27

Issue #299 (RFC-0002), authorized for implementation per
docs/architecture/REPOSITORY_LINEAGE_MIGRATION_PLAN.md. Adds the durable
owner-scoped logical grouping above repository revisions: a new
``repository_lineages`` table, nullable ``repositories.lineage_id`` /
``repositories.sequence`` columns, and a strict, deterministic backfill for
resolvable historical GitHub commits.

This is deliberately split into two revisions (plan §7). This one creates
every constraint that does *not* require the second table to already exist,
runs the backfill, verifies it, then closes every constraint that only needs
one side of the eventual cyclic integrity boundary. The genuinely cyclic
constraint -- the lineage's latest-member pointer proving it names a
repository in that exact lineage -- is Revision B
(0014_lineage_constraints), so a failure here leaves this revision's state
additive, backward-compatible, and inspectable before retrying B.

Backfill scope (plan §6): only ``source='github'`` rows with a valid 40-hex
commit SHA, a resolved ``refs/heads/...``/``refs/tags/...`` ref, and a
``source_url`` matching one of the exact accepted historical GitHub URL
forms are grouped into a lineage. Uploads, unresolved-ref rows, and anything
outside that strict grammar stay unlineaged standalone imports -- this
migration never guesses a grouping from a name, path, or network call.

Imports must be quiesced while this migration runs; there is no dual-write
compatibility for a concurrent insert racing the backfill.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from alembic import op
import sqlalchemy as sa

revision = "0013_lineage_expand"
down_revision = "0012_waitlist_entries"
branch_labels = None
depends_on = None

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REF_RE = re.compile(r"^refs/(?:heads|tags)/[A-Za-z0-9._/-]+$")
# The host is matched case-insensitively (scoped to just that group) because
# the host itself is one of the two things plan §6.1 step 3 requires
# case-folding -- a historical pre-hardening URL may have used "GitHub.com".
# The scheme/userinfo-marker literals stay exact-case; only the host is
# case-variable here.
_HTTPS_GITHUB_RE = re.compile(r"^https://(?i:github\.com)/([^/]+)/([^/]+?)(?:\.git)?/?$")
_SSH_GITHUB_RE = re.compile(r"^git@(?i:github\.com):([^/]+)/([^/]+?)(?:\.git)?$")
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

_CANONICAL_PARTIAL_WHERE = sa.text("canonical_source_key IS NOT NULL AND canonical_branch IS NOT NULL")

# Fixed, migration-local UUIDv5 namespace for deterministic backfill lineage
# IDs (plan §6.2). Frozen forever once this revision ships, exactly like
# every other literal in an applied migration -- never imported from, or
# shared with, live application code, which is free to evolve independently.
_BACKFILL_UUID_NAMESPACE = uuid.UUID("ac9ac65f-f0c1-4f7f-8147-9dc3509b4eaa")


def _safe_component(value: str) -> bool:
    return bool(_SAFE_COMPONENT_RE.fullmatch(value)) and ".." not in value


def _canonical_github_source(source_url: str | None) -> str | None:
    """Strict, conservative GitHub URL canonicalization, backfill-only (plan
    §6.1). Returns ``None`` for anything outside the exact accepted forms --
    the row then stays an unlineaged standalone import, never a guess.

    Deliberately not shared with ``app.services.repository_service``'s live
    parser (which only needs to handle its own validator's already-narrow
    output): a future change to that live code must never silently change
    what this frozen, already-applied migration replays.
    """
    if not source_url:
        return None
    trimmed = source_url.strip()
    match = _HTTPS_GITHUB_RE.match(trimmed) or _SSH_GITHUB_RE.match(trimmed)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    if not (_safe_component(owner) and _safe_component(repo)):
        return None
    return f"github.com/{owner.lower()}/{repo.lower()}"


def _lineage_id_for(owner_id: str, canonical_source_key: str, canonical_branch: str) -> str:
    """Deterministic, length-delimited encoding (plan §6.2) -- avoids the
    ambiguity a plain concatenation would have (e.g. two different
    owner/key/branch triples producing the same joined string)."""
    encoded = (
        f"{len(owner_id)}:{owner_id}|"
        f"{len(canonical_source_key)}:{canonical_source_key}|"
        f"{len(canonical_branch)}:{canonical_branch}"
    )
    return str(uuid.uuid5(_BACKFILL_UUID_NAMESPACE, encoded))


def _create_lineage_table() -> None:
    op.create_table(
        "repository_lineages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_source_key", sa.Text(), nullable=True),
        sa.Column("canonical_branch", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        # The cyclic half of this column's FK (proving the pointer names a
        # repository in *this* lineage) is Revision B; it is a plain nullable
        # column here.
        sa.Column("latest_repository_id", sa.String(length=36), nullable=True),
        sa.Column("next_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "owner_id", name="uq_repository_lineages_id_owner"),
        sa.CheckConstraint(
            "(canonical_source_key IS NULL AND canonical_branch IS NULL) OR "
            "(canonical_source_key IS NOT NULL AND canonical_branch IS NOT NULL)",
            name="ck_repository_lineages_canonical_pair",
        ),
        sa.CheckConstraint("next_sequence >= 1", name="ck_repository_lineages_next_sequence_positive"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_repository_lineages_owner_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_repository_lineages_owner_id", "repository_lineages", ["owner_id"])
    op.create_index(
        "uq_repository_lineages_owner_source_branch",
        "repository_lineages",
        ["owner_id", "canonical_source_key", "canonical_branch"],
        unique=True,
        sqlite_where=_CANONICAL_PARTIAL_WHERE,
        postgresql_where=_CANONICAL_PARTIAL_WHERE,
    )


def _add_repository_lineage_columns() -> None:
    # Both additions in one batch block (plan §7 step 2): avoids a second
    # SQLite table copy for what is otherwise the same operation.
    with op.batch_alter_table("repositories") as batch:
        batch.add_column(sa.Column("lineage_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("sequence", sa.Integer(), nullable=True))


def _repositories_core_table() -> sa.TableClause:
    return sa.table(
        "repositories",
        sa.column("id", sa.String()),
        sa.column("owner_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("source", sa.String()),
        sa.column("source_url", sa.Text()),
        sa.column("revision_kind", sa.String()),
        sa.column("revision_value", sa.String()),
        sa.column("revision_ref", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("lineage_id", sa.String()),
        sa.column("sequence", sa.Integer()),
    )


def _lineages_core_table() -> sa.TableClause:
    return sa.table(
        "repository_lineages",
        sa.column("id", sa.String()),
        sa.column("owner_id", sa.String()),
        sa.column("canonical_source_key", sa.Text()),
        sa.column("canonical_branch", sa.Text()),
        sa.column("display_name", sa.Text()),
        sa.column("latest_repository_id", sa.String()),
        sa.column("next_sequence", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
    )


def _eligible_groups(connection: sa.Connection, repositories: sa.TableClause) -> dict[tuple[str, str, str], list[dict]]:
    """Group resolvable historical GitHub rows by (owner, canonical source,
    canonical branch), sorted deterministically within each group (plan
    §6.1/§6.2). Everything else (uploads, unresolved refs, malformed/foreign
    source URLs) is excluded and stays standalone."""
    rows = connection.execute(
        sa.select(
            repositories.c.id,
            repositories.c.owner_id,
            repositories.c.name,
            repositories.c.source,
            repositories.c.source_url,
            repositories.c.revision_kind,
            repositories.c.revision_value,
            repositories.c.revision_ref,
            repositories.c.created_at,
        )
    ).mappings()

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row["source"] != "github" or row["revision_kind"] != "git":
            continue
        revision_value = row["revision_value"]
        if not revision_value or not _GIT_SHA_RE.fullmatch(revision_value):
            continue
        revision_ref = row["revision_ref"]
        if not revision_ref or not _REF_RE.fullmatch(revision_ref):
            continue
        canonical_source_key = _canonical_github_source(row["source_url"])
        if canonical_source_key is None:
            continue
        key = (row["owner_id"], canonical_source_key, revision_ref)
        groups.setdefault(key, []).append(dict(row))

    for members in groups.values():
        members.sort(key=lambda member: (member["created_at"], member["id"]))
    return groups


def _backfill_lineages() -> dict[tuple[str, str, str], list[dict]]:
    connection = op.get_bind()
    repositories = _repositories_core_table()
    lineages = _lineages_core_table()

    groups = _eligible_groups(connection, repositories)

    for (owner_id, canonical_source_key, canonical_branch), members in groups.items():
        lineage_id = _lineage_id_for(owner_id, canonical_source_key, canonical_branch)
        first, last = members[0], members[-1]
        next_sequence = len(members) + 1

        already_present = connection.execute(sa.select(lineages.c.id).where(lineages.c.id == lineage_id)).first()
        if already_present is None:
            connection.execute(
                lineages.insert().values(
                    id=lineage_id,
                    owner_id=owner_id,
                    canonical_source_key=canonical_source_key,
                    canonical_branch=canonical_branch,
                    display_name=first["name"],
                    latest_repository_id=last["id"],
                    next_sequence=next_sequence,
                    created_at=first["created_at"],
                )
            )
        else:
            # A prior interrupted run already created this row (plan §6.2/§7
            # "interruption and rerun"): reconcile its counter and latest
            # pointer to this deterministic grouping rather than trusting
            # whatever a partial run left behind.
            connection.execute(
                lineages.update()
                .where(lineages.c.id == lineage_id)
                .values(latest_repository_id=last["id"], next_sequence=next_sequence)
            )

        for index, member in enumerate(members, start=1):
            connection.execute(
                repositories.update()
                .where(repositories.c.id == member["id"])
                .values(lineage_id=lineage_id, sequence=index)
            )

    return groups


def _verify_backfill(groups: dict[tuple[str, str, str], list[dict]]) -> None:
    """Abort the migration unless every §6.4 invariant holds. Reuses the same
    grouping the write phase just used (rather than re-deriving the
    eligibility predicate a second time in SQL), so this proves the write
    actually took effect as intended, not just that a second, possibly
    independently-buggy, predicate agrees with the first."""
    connection = op.get_bind()
    repositories = _repositories_core_table()
    lineages = _lineages_core_table()

    touched = 0
    for (owner_id, canonical_source_key, canonical_branch), members in groups.items():
        lineage_id = _lineage_id_for(owner_id, canonical_source_key, canonical_branch)
        lineage_row = (
            connection.execute(
                sa.select(lineages.c.owner_id, lineages.c.latest_repository_id, lineages.c.next_sequence).where(
                    lineages.c.id == lineage_id
                )
            )
            .mappings()
            .first()
        )
        if lineage_row is None:
            raise RuntimeError(f"Lineage backfill verification failed: {lineage_id} is missing after backfill.")
        if lineage_row["owner_id"] != owner_id:
            raise RuntimeError(f"Lineage backfill verification failed: {lineage_id} has the wrong owner.")
        if lineage_row["latest_repository_id"] != members[-1]["id"]:
            raise RuntimeError(f"Lineage backfill verification failed: {lineage_id} latest pointer is wrong.")
        if lineage_row["next_sequence"] != len(members) + 1:
            raise RuntimeError(f"Lineage backfill verification failed: {lineage_id} next_sequence is wrong.")

        seen_sequences: set[int] = set()
        for index, member in enumerate(members, start=1):
            repo_row = (
                connection.execute(
                    sa.select(repositories.c.lineage_id, repositories.c.sequence, repositories.c.owner_id).where(
                        repositories.c.id == member["id"]
                    )
                )
                .mappings()
                .first()
            )
            if repo_row is None or repo_row["lineage_id"] != lineage_id or repo_row["sequence"] != index:
                raise RuntimeError(
                    f"Lineage backfill verification failed: repository {member['id']} is not "
                    f"correctly attached to lineage {lineage_id}."
                )
            if repo_row["owner_id"] != owner_id:
                raise RuntimeError(f"Lineage backfill verification failed: repository {member['id']} owner mismatch.")
            if repo_row["sequence"] in seen_sequences:
                raise RuntimeError(f"Lineage backfill verification failed: duplicate sequence in lineage {lineage_id}.")
            seen_sequences.add(repo_row["sequence"])
            touched += 1

    stray = connection.execute(
        sa.select(sa.func.count())
        .select_from(repositories)
        .where(sa.or_(repositories.c.lineage_id.isnot(None), repositories.c.sequence.isnot(None)))
    ).scalar()
    if stray != touched:
        raise RuntimeError(
            f"Lineage backfill verification failed: {stray} repositories carry a lineage "
            f"attachment, expected exactly {touched} from the eligible groups."
        )


def _add_repository_lineage_constraints() -> None:
    with op.batch_alter_table("repositories") as batch:
        batch.create_check_constraint(
            "ck_repositories_lineage_sequence_pair",
            "(lineage_id IS NULL AND sequence IS NULL) OR "
            "(lineage_id IS NOT NULL AND sequence IS NOT NULL AND sequence >= 1)",
        )
        # Every NULL is distinct under SQL uniqueness, so standalone rows
        # (both null) never collide here (plan §4.2).
        batch.create_unique_constraint("uq_repositories_lineage_sequence", ["lineage_id", "sequence"])
        # Composite target proving a lineage's latest-member pointer names a
        # repository that actually belongs to that exact lineage (used by
        # Revision B's FK).
        batch.create_unique_constraint("uq_repositories_id_lineage", ["id", "lineage_id"])
        batch.create_foreign_key(
            "fk_repositories_lineage_owner",
            "repository_lineages",
            ["lineage_id", "owner_id"],
            ["id", "owner_id"],
            deferrable=True,
            initially="DEFERRED",
        )


def upgrade() -> None:
    _create_lineage_table()
    _add_repository_lineage_columns()
    groups = _backfill_lineages()
    _verify_backfill(groups)
    _add_repository_lineage_constraints()


def downgrade() -> None:
    # New grouping/counter data is lost; every pre-existing repository
    # column and value is preserved (plan §7/§11).
    with op.batch_alter_table("repositories") as batch:
        batch.drop_constraint("fk_repositories_lineage_owner", type_="foreignkey")
        batch.drop_constraint("uq_repositories_id_lineage", type_="unique")
        batch.drop_constraint("uq_repositories_lineage_sequence", type_="unique")
        batch.drop_constraint("ck_repositories_lineage_sequence_pair", type_="check")
        batch.drop_column("sequence")
        batch.drop_column("lineage_id")

    op.drop_index("uq_repository_lineages_owner_source_branch", table_name="repository_lineages")
    op.drop_index("ix_repository_lineages_owner_id", table_name="repository_lineages")
    op.drop_table("repository_lineages")
