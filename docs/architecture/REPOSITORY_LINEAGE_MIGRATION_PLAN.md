# Repository Lineage — Alembic Migration & Implementation Plan

| Field | Value |
| --- | --- |
| Planning issue | [#299](https://github.com/Second-Origin/PARTHA/issues/299) |
| Governing design | [RFC-0002](REPOSITORY_LINEAGE_RFC.md) |
| Live-code baseline | `origin/dev` at `373306d` |
| Purpose | Specify the proposed migration mechanics, backfill, integrity rules, and validation for #299 |
| Runtime changes in this document | None |
| Authorization status | **Architecture amendment pending explicit owner approval in PR #328** |

This document is an implementation-grade plan, not an implementation. It does not create an
Alembic revision, change an ORM model, change `RepositoryService`, or alter an API/frontend
contract. It records the current schema and specifies a safe migration and backfill. RFC-0002 is the
architecture contract; this plan defines the migration and test mechanics without extending it.

## 1. Executive verdict

**#299 NOT AUTHORIZED FOR IMPLEMENTATION.**

The migration can be implemented safely once the owner explicitly approves the architecture
amendment in RFC-0002. Its two implementation-critical decisions are:

1. Uploads and unresolved legacy GitHub rows are **unlineaged standalone imports**: their lineage
   fields are null and no synthetic lineage exists.
2. A race-free, non-reusing sequence needs durable allocation state. RFC-0002 now specifies
   `repository_lineages.next_sequence`, 1-based ordinals, transactional allocation, valid deletion
   gaps, and preservation of empty lineages.

Explicit owner approval of PR #328 changes the authorization state to **#299 AUTHORIZED FOR
IMPLEMENTATION**. #322 remains required before the eventual #299 implementation PR merges, but it
does not block writing or testing that implementation after architecture approval. No runtime or
migration implementation is present here.

## 2. Current-state data model

### 2.1 What a `RepositoryRecord` means today

One `repositories` row is primarily **one imported immutable revision**, but it also owns the
mutable import/analysis workspace for that revision:

- GitHub: `revision_kind = 'git'`, `revision_value` is the 40-character lowercase commit SHA, and
  `revision_ref` is a resolved `refs/heads/...` or `refs/tags/...` value.
- Upload: `revision_kind = 'upload'`, `revision_value` is the hash of the uploaded archive bytes,
  and `revision_ref` is `NULL`.
- The row owns a distinct `local_path`, parsed `file_tree`, parser metadata, size/count fields, and
  mutable analysis status/progress/timestamps.
- An import attempt that fails before insertion is not a row. An exact duplicate rejected by the
  service is not another import-event row. The table is therefore neither a pure logical
  repository nor an import-event log.

The right description is: **one persisted imported revision plus its revision-local workspace and
lifecycle state**. RFC-0002 correctly needs a separate logical grouping above it.

### 2.2 Relevant tables

#### `users`

Introduced by `0002_users_and_repo_owner`; `password_hash` was added by `0003_auth_credentials`.

- PK: `id` (`String(36)`).
- Unique/index: `email` (`String(320)`) through unique index `ix_users_email`.
- Non-null: `id`, `email`, `is_active`, `created_at`, `updated_at`.
- Nullable: `password_hash` (the seed user deliberately cannot authenticate).
- Ownership root: repositories and other owner-scoped tables ultimately cascade from `users.id`;
  `0010_account_deletion` finalized the explicit database cascades.

#### `repositories`

Introduced by `0001_initial`; `owner_id` by `0002`; revision columns/constraints by `0005`; the
placeholder `data_source` was removed by `0007`; owner cascade was normalized by `0010`.

- PK: `id` (`String(36)`).
- FK: `owner_id -> users.id`, named `fk_repositories_owner_id_users`, `ON DELETE CASCADE`.
- Required fields: `id`, `owner_id`, `name`, `source`, `local_path`, `size`, `file_count`, `status`,
  `analysis_progress`, `uploaded_at`, `file_tree`, `created_at`, `updated_at`.
- Nullable fields: `description`, `source_url`, `branch`, all three revision fields (to preserve
  unidentified legacy rows), `analysis_stage`, `analysed_at`, `error_message`, `repo_metadata`.
- Unique: `uq_repositories_id_revision(id, revision_kind, revision_value)`. Because `id` is already
  the PK, this is principally the composite FK target used by snapshots/jobs; it does not dedupe
  commits across repository rows.
- Checks: revision kind; all-or-none revision completeness; exact upload hash shape; exact Git SHA
  and `refs/...` shape.
- Indexes: owner, name, source, status, and `ix_repositories_revision_value`.
- There is no unique database constraint for current service-level GitHub or upload duplicate
  detection.

`source_url`, `branch`, and `repo_metadata` are descriptive/mutable import data. Only the typed
revision columns are revision identity. Historical `repo_metadata['intelligence']` can remain, but
all executable Repository Intelligence consumers use sealed snapshots.

#### `ri_snapshots` and Repository Intelligence persistence

Introduced by `0005_revision_snapshots`.

- `ri_snapshots` PK: `snapshot_id` (`String(48)`).
- Composite FK:
  `(repository_id, revision_kind, revision_value) -> repositories(id, revision_kind,
  revision_value)`, named `fk_ri_snapshots_repository_revision`, `ON DELETE CASCADE`.
- Snapshot identity/lifecycle fields are non-null except `revision_ref`, graph hash, actual
  producers, failure code, and sealed timestamp as allowed by state.
- Indexes include repository lookup, repository+revision lookup, and the partial unique completed
  semantic identity over `(repository_id, revision_value, schema_version, producer_set_hash,
  config_hash)`.
- `ri_nodes`, `ri_edges`, `ri_assertions`, `ri_observations`, `ri_evidence`, `ri_derivations`, and
  `ri_diagnostics` all refer to `ri_snapshots.snapshot_id` with cascade deletion. Their
  same-snapshot composite constraints prevent cross-snapshot fact leakage.

All normalized child tables were introduced by `0005`; the two directional edge indexes were added
by `0008`:

- `ri_nodes`: integer PK `id`; all fields required except `name`, `language`, and `properties`;
  unique `(snapshot_id, stable_key)` and `(snapshot_id, id)`; snapshot index; partial unique root
  index; snapshot FK cascades.
- `ri_edges`: integer PK `id`; all fields required; unique snapshot edge ID, resolved triple, and
  `(snapshot_id, id)`; both endpoint composite FKs resolve to nodes in the same snapshot and
  cascade; indexes on snapshot and both `(snapshot, endpoint, predicate)` directions.
- `ri_assertions`: integer PK `id`; all fields required; unique snapshot assertion ID and
  `(snapshot_id, id)`; same-snapshot subject-node FK cascades; snapshot index.
- `ri_observations`: integer PK `id`; only `referent_text` nullable; unique snapshot observation ID
  and `(snapshot_id, id)`; same-snapshot subject-node FK cascades; positive ordinal check and
  snapshot index.
- `ri_evidence`: integer PK `id`; exactly one of `node_ref`, `edge_ref`, or `observation_ref` is
  non-null; all span/extractor fields required; same-snapshot composite parent FKs cascade; indexes
  for snapshot and each parent; three partial unique fact indexes prevent duplicate evidence for
  each parent kind.
- `ri_derivations`: integer PK `id`; exactly one of `edge_ref`/`assertion_ref` is non-null;
  `ref_kind` and `ref_identity` required; same-snapshot composite parent FKs cascade; snapshot index
  and two partial unique derivation indexes.
- `ri_diagnostics`: integer PK `id`; path/span/subject/object/details nullable, all diagnostic
  identity/message/producer fields required; snapshot FK cascades; snapshot index and severity/span/
  relative-path checks.

Lineage does not change any of these keys. A snapshot remains an immutable artifact of one
repository row/revision.

#### `analysis_jobs`

Introduced by `0006_analysis_jobs`.

- PK: `id` (`String(36)`).
- Composite repository-revision FK with `ON DELETE CASCADE`.
- `owner_id -> users.id` with `ON DELETE CASCADE`.
- Optional `snapshot_id -> ri_snapshots.snapshot_id` with `ON DELETE SET NULL`.
- Required identity/state includes repository, owner, revision kind/value, config hash, status,
  progress, attempts, cancellation flag, and timestamps.
- Partial unique indexes protect one effective job identity and one non-null snapshot association.

Jobs remain revision-scoped, not lineage-scoped.

#### Other direct repository identity references

- `ai_conversation_messages` (`0009`): PK `id`; owner FK and repository FK both cascade; required
  integer `sequence`; unique `(owner_id, repository_id, sequence)`. Conversation history remains
  attached to one imported revision.
- Account deletion (`0010`): `users` deletion cascades repository rows, which cascade their
  snapshots, jobs, and AI turns. The non-PII `account_deletion_audits` table deliberately has no
  user FK.
- `ai_provider_configs` and `refresh_tokens` are owner-scoped but do not reference repository
  identity.

## 3. RFC-0002 to live-code mapping

| RFC requirement | Status at baseline | Mapping / discrepancy |
| --- | --- | --- |
| A repository row is one immutable imported revision | Implemented | Typed revision columns and snapshot/job composite FKs implement this. The row also owns mutable revision-local lifecycle/workspace state. |
| Durable logical lineage above revisions | Absent | No lineage model, table, repository FK, query, or API field exists. |
| Key `(owner_id, canonical_source_key, canonical_branch)` | Absent | Current dedupe uses exact stored `source_url`, commit, owner. No canonical source field exists. |
| GitHub URL normalization accepts HTTPS/SSH variants | Incompatible/partial | Live imports accept only lowercase-host public HTTPS URLs. RFC examples also include mixed-case host and `git@github.com:` syntax. Backfill can normalize only strictly recognized historical values; live validation must not be broadened implicitly by #299. |
| Branch-scoped identity | Partial input exists | `revision_ref` is normalized to `refs/heads/...` or `refs/tags/...`; `branch` is only the requested input. The canonical component must be `revision_ref` verbatim, not `branch`. The RFC calls this `canonical_branch` even when it is a tag. |
| Upload/unresolved-ref imports are unlineaged standalone imports | Defined by amended RFC | §4.3/§6 require no lineage row and null repository lineage fields. Live GitHub imports reject an unresolved ref, so only legacy GitHub rows can hit that case. |
| `repository_lineages` fields in §5.1 | Absent from code; defined by amended RFC | The architecture includes the durable counter, canonical-pair check, and same-lineage latest-pointer integrity implemented by this plan. |
| Partial unique canonical key | Defined by amended RFC | The canonical pair check and non-null partial uniqueness are architecture; this plan supplies exact DDL and migration ordering. |
| `repositories.lineage_id` and `sequence` | Absent | They must remain nullable permanently if §4.3/§6 is followed, not merely during expansion. |
| Monotonic sequence | Defined by amended RFC | Starts at 1, is allocated transactionally from `next_sequence`, is unique per lineage, and is never reused; deletion gaps are valid. |
| `latest_repository_id` rolls back on deletion | Incompatible with simple FK alone | `SET NULL` can clear the pointer but cannot choose the next-highest sequence. Service-level deletion must update it before deleting the revision, in the same transaction. |
| Earliest name and created-at ordering | Partial data exists | Both columns exist, but timestamp ties require `id` as a deterministic secondary sort key. |
| Idempotent backfill | Partially specified | Grouping inputs are reproducible, but random lineage IDs/inserts are not. Use a documented UUIDv5 namespace for backfill lineage IDs plus upsert/reconciliation logic. |
| No API/frontend change | Compatible | Lineage fields can remain internal. Existing response schemas need no change. |
| Snapshot immutability/identity unchanged | Compatible | Snapshots continue pointing to repository rows. |

### Architecture amendments captured in RFC-0002

1. **Standalone semantics.** The RFC now uses “unlineaged standalone import” and states that no
   synthetic lineage exists.
2. **Sequence state.** The RFC now requires a durable per-lineage counter, 1-based never-reused
   ordinals, transactional allocation, and valid deletion gaps.
3. **Latest-pointer and owner integrity.** The RFC now requires the composite membership and
   latest-member foreign keys; this plan supplies their exact names and migration order.
4. **Canonical-pair integrity.** The RFC now requires both canonical fields to be null or non-null
   together; this plan supplies the check and partial-index mechanics.
5. **Repeatable backfill.** The RFC requires deterministic identity and reconciliation; this plan
   owns the UUID construction, verification, interruption recovery, and downgrade mechanics.

## 4. RFC target schema

### 4.1 `repository_lineages`

| Column | Type/nullability | Rule |
| --- | --- | --- |
| `id` | `String(36)`, PK, non-null | UUID4 for new live lineages; deterministic UUID5 for backfill. |
| `owner_id` | `String(36)`, non-null | FK to `users.id`, `ON DELETE CASCADE`. |
| `canonical_source_key` | `Text`, nullable | Strict canonical GitHub key, e.g. `github.com/acme/widgets`; null only for a future manually created upload lineage. |
| `canonical_branch` | `Text`, nullable | Exact normalized `revision_ref`, including `refs/heads/` or `refs/tags/`. |
| `display_name` | `Text`, non-null | Permanently copied from the first repository row. |
| `latest_repository_id` | `String(36)`, nullable | Current highest surviving sequence; null for an empty lineage. |
| `next_sequence` | `Integer`, non-null | RFC-required next never-issued ordinal; initial value 1; check `>= 1`. |
| `created_at` | timezone-aware `DateTime`, non-null | Earliest member's `created_at` for backfill; current UTC for live creation. |

Constraints/indexes:

- `uq_repository_lineages_id_owner(id, owner_id)` as the composite ownership FK target.
- `ck_repository_lineages_canonical_pair`: source key and canonical branch are either both null or
  both non-null.
- partial unique index
  `uq_repository_lineages_owner_source_branch(owner_id, canonical_source_key, canonical_branch)`
  where both canonical fields are non-null. This is also the owner-scoped matching index.
- an index on `owner_id` for owner deletion/listing where the canonical lookup index is not used.
- a same-lineage latest-pointer FK described below.

Do not add provider type, GitHub numeric repository ID, upload hash, mutable source metadata, or a
JSON metadata bag. Current code does not provide a reliable provider-stable ID and RFC-0002 does
not authorize those fields.

### 4.2 New `repositories` columns and constraints

- `lineage_id String(36) NULL`.
- `sequence Integer NULL`.
- `ck_repositories_lineage_sequence_pair`: both are null or both are non-null, and a non-null
  sequence is at least 1.
- `uq_repositories_lineage_sequence(lineage_id, sequence)`. Because SQL uniqueness permits multiple
  null pairs, standalone rows do not collide. This index also serves ordered lineage reads.
- `uq_repositories_id_lineage(id, lineage_id)` as the target that proves a latest pointer belongs
  to the named lineage.
- composite ownership FK
  `(lineage_id, owner_id) -> repository_lineages(id, owner_id)`, named
  `fk_repositories_lineage_owner`, deferrable/initially deferred, with no automatic delete action.
  This makes cross-owner attachment impossible at the database layer.
- composite latest-member FK
  `repository_lineages(latest_repository_id, id) -> repositories(id, lineage_id)`, named
  `fk_repository_lineages_latest_member`, deferrable/initially deferred, with no automatic delete
  action. This prevents a latest pointer to another lineage or owner.

These RFC-required cyclic FKs are intentional and require ordered writes: insert a lineage with a
null latest pointer, insert/attach the repository, then set latest; on deletion, set latest to the
replacement or null before deleting the repository. Deferral permits these operations in one transaction.
Both dialects must be tested; if SQLite's batch/reflection path cannot preserve the deferrable
composite constraints, implementation must stop rather than silently weaken owner integrity.

`lineage_id` and `sequence` remain nullable at final head because RFC §4.3/§6 explicitly keeps
uploads and unidentified legacy rows as unlineaged standalone imports. They must not be tightened
to `NOT NULL` by #299.

### 4.3 Sequence semantics

- First repository in a lineage has `sequence = 1`.
- A sequence is a never-reused import ordinal within that lineage, not commit time and not Git
  ancestry.
- Deleting a revision does not decrement `next_sequence` and does not renumber survivors.
- `latest_repository_id` means the surviving member with greatest sequence, not the greatest
  timestamp and not necessarily an analyzed/completed member.
- Backfilled sequences are dense only at migration time, ordered by `(created_at ASC, id ASC)`.

The RFC makes the ordinal 1-based, matching its “third import” language and avoiding a zero ordinal
in future internal tooling.

## 5. Concurrency design

### 5.1 Options evaluated

| Approach | PostgreSQL | SQLite/test | Failure/retry | Assessment |
| --- | --- | --- | --- | --- |
| Unlocked `MAX(sequence)+1` | Two transactions can choose the same value. | Same logical race; writer upgrade can also raise busy errors. | Unique conflict catches damage but requires full retry. | Unsafe as the primary allocator. |
| `SELECT ... FOR UPDATE` on lineage, then `MAX+1` | Correctly serializes existing-lineage allocation. | SQLite ignores row-level `FOR UPDATE`; database writer locking occurs later. | First-lineage creation still needs unique-conflict reconciliation. Highest-number deletion permits reuse. | Better on PostgreSQL, incomplete cross-dialect. |
| Retry only on `(lineage_id, sequence)` conflict | Correct if bounded and the transaction is fully retried. | Matches the existing AI-turn pattern, but can amplify lock contention. | Correctness comes from unique constraint; repeated conflicts eventually fail. | Viable fallback/defense, not deterministic allocation by itself. |
| Serializable transactions | Correct with serialization-failure retries. | SQLite semantics differ and writer contention is database-wide. | Every serialization failure requires transaction retry. | Excessive scope/complexity for one counter. |
| Global database sequence | Race-free but not per-lineage/dense. | SQLite has no equivalent PostgreSQL sequence object. | Creates gaps and non-portable behavior. | Reject. |
| Per-lineage `next_sequence` updated transactionally | Row update locks exactly one lineage. | The first update obtains SQLite's serialized writer lock; configured busy timeout bounds waiting. | Rollback restores the counter; unique constraint remains defense in depth. | **Selected by RFC-0002.** |

### 5.2 Allocation algorithm

After cloning/upload extraction and parsing succeed, perform all lineage and repository database
writes in one transaction:

1. Find the lineage by all three owner-scoped canonical key columns.
2. If absent, insert it with `next_sequence = 1` and null latest pointer. The partial unique index
   is the authority if two creators race.
3. Atomically update that one lineage row:

   ```sql
   UPDATE repository_lineages
      SET next_sequence = next_sequence + 1
    WHERE id = :lineage_id AND owner_id = :owner_id;
   ```

   Verify exactly one row changed, then read the row in the same transaction and allocate
   `sequence = next_sequence - 1`. The write lock remains held through commit on both databases.
   `UPDATE ... RETURNING` may be used only if the supported SQLite version is explicitly pinned and
   tested; update-then-read is portable.
4. While holding that serialization point, check whether this lineage already contains the same
   `revision_value`. If so, roll back and return the existing 409 behavior. This closes the current
   simultaneous same-commit race without requiring a backfill-breaking unique revision constraint.
5. Insert the repository with the allocated lineage/sequence and update the latest pointer.
6. Commit once. Any failure rolls back lineage creation, counter allocation, repository insertion,
   and latest-pointer change together.

If two transactions race to create the first canonical lineage, one wins the canonical-key unique
index. The loser rolls back, reloads the winning lineage by the owner-scoped key, and retries the
database phase a bounded number of times (five is consistent with `AiConversationRepository`). Only
the expected canonical-key or sequence constraint is reconciled; unrelated `IntegrityError`s are
re-raised.

The current `RepositoryRepository.add()` commits immediately, so #299 must add a transaction-aware
repository/lineage persistence path rather than composing existing `add()` calls. This is a scoped
requirement, not a general repository-layer refactor.

### 5.3 Filesystem/database failure boundary

Cloning/extraction/parsing remains outside the database transaction to avoid holding a DB lock
during slow I/O. The final DB phase owns no external side effect. If it fails—including a duplicate
won by another request—the newly staged repository directory must be removed, extending the
current pre-insert cleanup across the commit phase. A database commit that succeeds followed by an
HTTP serialization failure must not remove the committed repository directory.

## 6. Backfill design

### 6.1 Strict GitHub canonicalization

Backfill only a row satisfying all of these conditions:

- `source = 'github'`;
- `revision_kind = 'git'` with a valid existing revision value;
- `revision_ref` is a valid non-empty `refs/heads/...` or `refs/tags/...` value; and
- `source_url` parses as one of the RFC-supported, unambiguous GitHub repository forms:
  `https://github.com/<owner>/<repo>[.git]` (optionally followed by one trailing slash) or
  `git@github.com:<owner>/<repo>[.git]`, with exactly two path components and no query, fragment,
  port, user-info, traversal, or percent-encoded ambiguity.

Normalization:

1. Trim surrounding whitespace.
2. Parse one of the exact accepted forms; do not perform a generic string replacement.
3. Case-fold the host and both GitHub owner/repository components.
4. Remove one terminal `.git` and trailing slash.
5. Emit `github.com/<owner>/<repo>`.
6. Set `canonical_branch = revision_ref` verbatim. Git refs are case-sensitive; do not lowercase it.

Current live imports normally store normalized public HTTPS URLs, but historical pre-hardening rows
may not. A row outside the strict grammar stays standalone. The migration must not infer from
repository name, local path, file tree, metadata, current GitHub redirects, or network calls.

This cannot recognize a renamed/transferred GitHub repository as the same lineage because no
stable GitHub repository ID is stored. Different canonical owner/repository paths remain different
lineages. That limitation is truthful and is not rename/move detection.

### 6.2 Grouping and deterministic ordering

Group eligible rows by
`(owner_id, canonical_source_key, canonical_branch)`. For each group:

1. Sort rows by `(created_at ASC, id ASC)`; the primary-key tie-break makes ordering deterministic.
2. Derive the backfill lineage ID with UUIDv5 from a fixed, migration-local namespace and an
   unambiguous length-delimited encoding of the three group values.
3. Create/reconcile one lineage. `display_name` and `created_at` come from the first sorted row.
4. Assign sequences `1..N` in sorted order.
5. Set `latest_repository_id` to row `N` and `next_sequence = N + 1`.

UUIDv5 is only a migration recovery mechanism. Live imports use random UUIDs. The fixed namespace
and encoding must be constants in the revision and covered by a deterministic test.

Existing duplicate commit rows in one canonical group are preserved and ordered; deleting or
coalescing them would be data loss. The migration should report their count in test/preflight
evidence. Future serialized import logic prevents new duplicates within a lineage.

### 6.3 Uploads and unsupported metadata

Existing uploads contain an archive-byte hash, filename-derived name, extracted tree, and parser
metadata. None proves that two archives are revisions of the same logical repository. Uploads
therefore remain `lineage_id = NULL`, `sequence = NULL`; do not group by filename, archive hash,
tree similarity, repository name, or metadata.

GitHub rows with missing/corrupt source URL or unresolved ref receive the same null pair. This is
the safest deterministic behavior and follows RFC §6 literally. It means historical standalone
rows do not acquire a stable logical lineage under #299; resolving that requires a future manual
linking feature or a change to RFC-0002.

### 6.4 Backfill verification

Before final constraints, abort the migration unless all invariants hold:

- every eligible source group has exactly one lineage;
- every eligible repository has the expected lineage and a positive sequence;
- no ineligible/upload repository has either lineage field populated;
- owner IDs match on every attachment;
- each group has exactly sequences `1..N`, latest points to `N`, and next is `N+1`;
- each lineage's display name/created time comes from the deterministic first row;
- canonical fields are both null or both non-null; and
- no duplicate `(lineage_id, sequence)` exists.

Do not silently skip a failed update or coerce corrupt data to satisfy final constraints.

## 7. Concrete Alembic migration sequence

Use two new revisions after `0010_account_deletion`, each with an ID under the existing PostgreSQL
`alembic_version VARCHAR(32)` limit. Suggested IDs are `0011_lineage_expand` and
`0012_lineage_constraints`.

Imports must be quiesced while the migrations run. The application currently has no dual-write
compatibility for lineage and a concurrent repository insert could escape the backfill. Existing
read traffic may continue subject to the deployment platform's normal DDL locks.

### Revision A — expand and backfill

1. Create `repository_lineages` with all columns, PK, owner FK/cascade, canonical-pair and counter
   checks, `(id, owner_id)` unique target, canonical partial unique index, and owner index. Create it
   with `latest_repository_id` nullable but defer its repository-member FK until both sides exist.
2. Add nullable `repositories.lineage_id` and `repositories.sequence` in **one**
   `op.batch_alter_table('repositories')` block. Keeping additions together avoids repeated SQLite
   table copies.
3. Run the strict, deterministic backfill in bounded batches using SQLAlchemy Core tables defined
   inside the migration—not application models, which will evolve.
4. Run all §6.4 verification queries and fail explicitly on any mismatch.
5. Create the lineage-sequence pair check, unique sequence index, `(id, lineage_id)` unique target,
   and composite repository-to-lineage ownership FK. On SQLite, use batch mode with an explicit
   naming convention, following `0010_account_deletion`; never try to drop an anonymously reflected
   constraint later.

PostgreSQL: table creation/add-column are fast metadata operations; backfill and index creation
scan/write `repositories` and may lock writes. The migration is transactional. For a database large
enough that ordinary index creation is unacceptable, `CREATE INDEX CONCURRENTLY` would require a
non-transactional migration and a different recovery plan; current project policy/test shape favors
the transactional path.

SQLite: adding constraints requires batch recreation. Ensure `PRAGMA foreign_keys=ON`; batch mode
must preserve every existing named repository check, unique constraint, FK, and index. The
migration test must compare them, not only assert the new columns exist.

Downgrade is handled after Revision B's constraints are removed: drop new repository constraints,
indexes, and columns in batch, then drop `repository_lineages`. Existing repository data survives;
lineage-only grouping/counter data is intentionally lost.

### Revision B — close the cyclic integrity boundary

1. Add `fk_repository_lineages_latest_member(latest_repository_id, id) ->
   repositories(id, lineage_id)` as deferrable/initially deferred.
2. Re-run cross-table verification under the final constraints.

On SQLite this requires batch-recreating `repository_lineages`; use explicit names/naming
conventions. Splitting the cyclic constraint into a second revision makes recovery clear: if it
fails, Revision A is a backward-compatible additive state and can be inspected/fixed before
rerunning B. The new application must not start unless Alembic is at Revision B/head.

Revision B downgrade drops only the latest-member FK. Revision A downgrade then removes all
lineage additions. Full `head -> base -> head` remains required by project policy.

### Interruption and rerun

- PostgreSQL failure rolls back the active revision transaction.
- SQLite DDL/batch behavior must not be assumed identical; deterministic UUIDs and reconciliation
  make the backfill repeatable if an operator restores/stamps to Revision A and reruns.
- Never manually stamp past a failed backfill or constraint verification.
- If Revision A is recorded as applied and B fails, leave imports stopped, correct the data or
  migration, and rerun upgrade. Do not start code that assumes the latest-member invariant.
- Downgrade from a live lineage-aware application requires stopping that application first. It
  discards lineage records and new columns but preserves all pre-#299 repository/snapshot/job data.

## 8. Future import and deletion rules for #299

### 8.1 GitHub

After the existing clone resolves `revision_value` and `revision_ref`:

1. Canonicalize the already validated URL to `github.com/<lower-owner>/<lower-repo>`.
2. Use `revision_ref` verbatim as canonical branch/ref. Never use requested `branch` as identity.
3. Lookup only by owner plus both canonical values.
4. Create or reconcile the lineage, allocate the next sequence, dedupe the commit within that
   lineage, insert the repository, and update latest in one transaction (§5.2).
5. Do not make a network call during matching and do not follow GitHub rename redirects.

Different owners, canonical repositories, branches, or tags produce different lineages. The same
commit can legitimately occur in different branch-scoped lineages. Case variants and `.git` or
trailing-slash variants converge only after URL validation; broadening live input to SSH/mixed-case
host is outside #299 unless separately approved.

### 8.2 Upload and unresolved ref

`import_uploaded_repository` continues exact owner-scoped archive-hash duplicate detection but
sets both lineage fields null. It does not create or search a lineage. This is why #299 can touch
the upload path without inventing upload identity: the implementation makes the standalone rule
explicit.

Live GitHub imports currently fail if no resolved ref is available. Preserve that behavior; do not
use #299 to introduce raw-SHA import. Legacy unresolved rows remain null after migration.

The existing simultaneous-upload duplicate race is not a lineage allocation race. A database
partial unique index for uploads would close it, but that is a separate change with historical-data
preflight implications and should not be smuggled into #299. Record it as follow-up if the
concurrency test proves it matters.

### 8.3 Repository deletion

Replace the current delete commit boundary with one transaction:

1. Owner-scope the repository and, if lineaged, lock/update its lineage counter row.
2. If deleting `latest_repository_id`, select the surviving member with greatest sequence and set
   latest to that ID, or null if none.
3. Delete the repository row (which cascades snapshots/jobs/AI turns).
4. Commit, then remove the filesystem path. The current code deletes storage before DB commit; #299
   should reverse this order or explicitly handle DB failure so a failed FK/update cannot leave a
   database row whose source directory has already vanished.

Keep empty lineages. Their canonical identity and `next_sequence` preserve stable matching and
never-reused ordering for a later import. Garbage collection is future work.

Account deletion continues to delete the user in one transaction. Both repository and lineage
owner FKs cascade. The cyclic, deferred member FKs must be exercised on real PostgreSQL and SQLite
to prove all rows disappear without cross-owner effects.

## 9. Ownership and security invariants

- Every canonical lookup includes `owner_id`; never lookup a lineage by canonical source alone.
- The repository-to-lineage composite FK makes a cross-owner attachment invalid even if service
  code is wrong.
- The latest-member composite FK ensures the pointer names a repository in that exact lineage.
- Repository and lineage identifiers are never added to public responses in #299. Existing
  owner-scoped 404 behavior remains unchanged, so IDs cannot probe another owner's history.
- There is no cross-owner comparison or organization lineage.
- User deletion cascades only from one `users.id`; no lineage is shared by owners, so another
  user's repository cannot be reached by cascade.
- Canonical keys are identifiers, not authorization. They must not be logged with repository
  contents or used to bypass owner scoping.

## 10. Snapshot and future-evolution boundaries

Snapshots continue to point to a `repositories` row and exact revision. No snapshot column,
constraint, query contract, API route, response schema, or frontend surface changes in #299.
Multiple revisions in one lineage expose their snapshots exactly as they do now: through their
individual repository IDs. Lineage-aware history APIs are later work.

#299 establishes only:

- stable owner-scoped logical grouping for resolvable GitHub branch/tag imports;
- deterministic repository ordering and a current surviving member pointer;
- migration/backfill and import-time assignment; and
- integrity/ownership foundations for later revision-aware queries.

It thereby enables—but does not implement—two-revision comparison, snapshot/graph diff,
architecture drift, change-impact analysis, and cross-revision node/fact identity. It does not add
graph diff, impact scoring, rename/move detection, historical UI, PR review, architecture drift,
incremental analysis, new snapshot contracts, or manual upload linking.

## 11. Failure modes and required behavior

| Scenario | Required behavior |
| --- | --- |
| Same GitHub repo/branch, different commits concurrently | Both serialize on the lineage counter; distinct increasing sequences; latest is the later allocation. |
| Same GitHub commit concurrently, existing lineage | First wins; second observes duplicate after serialization and returns conflict; no orphan DB row/directory. |
| First-ever same lineage concurrently | Canonical unique index chooses one lineage; loser reloads/retries; no duplicate lineage. |
| Different lineage imports concurrently | PostgreSQL locks different rows; SQLite serializes writers as it does today; no shared counter. |
| Failed import before DB phase | No lineage/repository row; staged files cleaned. |
| DB failure after counter allocation | Whole transaction rolls back, including the counter/latest changes; staged files cleaned. |
| Repository deletion | Latest rolls back to highest surviving sequence; counter never decreases; snapshots/jobs/turns cascade. |
| Last revision deleted | Empty lineage remains with null latest and preserved next sequence. |
| User deletion | Repositories and lineages cascade for that owner only; audit survives. |
| Corrupt historical metadata | Row remains standalone; migration never guesses. |
| Migration interruption | Active revision rolls back where supported; deterministic reconciliation supports controlled rerun; never stamp past verification. |
| Downgrade | New grouping data is lost; all pre-existing repository/revision/snapshot data is preserved. |
| SQLite writer contention | Busy timeout bounds waiting; atomic counter update serializes; tests must use separate connections/threads. |
| PostgreSQL concurrency | Row update provides real row-level serialization; test with separate transactions in CI. |

## 12. Authorization gate

PR #328 does not implement #299. Before the owner explicitly approves PR #328's architecture
amendment, **#299 is not authorized for implementation**. That approval may authorize writing and
testing the #299 implementation; it does not remove the separate requirement that
[#322](https://github.com/Second-Origin/PARTHA/issues/322) be complete before the eventual #299
implementation PR merges.

## 13. Test matrix for implementation

### Migration tests

- Fresh empty DB: `base -> head`, expected tables/columns/named constraints/indexes, then
  `head -> base -> head`.
- Populated DB at `0010`: multiple commits in one URL/ref become one lineage; different refs,
  repositories, and owners do not.
- URL variants normalize exactly as approved; malformed/ambiguous URLs remain null.
- Deterministic timestamp ties use repository ID.
- Uploads, unresolved refs, unidentified legacy rows remain null/null.
- Existing duplicate commits are preserved without sequence collision.
- Display name/created time/latest/next counter are correct.
- Backfill rerun/reconciliation is deterministic.
- Existing repository revision checks/FKs/indexes survive SQLite batch recreation.
- Downgrade preserves all old columns and data, while documenting loss of lineage-only data.
- Account-delete cascades work after migration.
- Run all above on local SQLite and the isolated real PostgreSQL database used by
  `PARTHA_TEST_PG_URL` CI.

### Service tests

- First GitHub revision creates lineage with sequence 1 and next 2.
- Subsequent commit on same canonical source/ref reuses lineage and increments.
- URL case/`.git`/trailing-slash variants allowed by live validation match as specified.
- Different repository, ref/tag, or owner gets a different lineage.
- Same commit in different branch lineages is allowed.
- Upload sets null/null and preserves current response contract.
- Unresolved Git ref still fails import.
- Failed clone/parse leaves no DB row; failed DB insert cleans staged storage.
- Deleting non-latest leaves latest unchanged; deleting latest rolls back; deleting last keeps empty
  lineage; next import never reuses a sequence.
- Cross-owner lineage lookup/attachment returns indistinguishable not-found behavior at service
  boundaries and fails the composite FK if forced directly.

### Concurrency/integrity tests

- Two different commits imported into an existing lineage receive unique consecutive sequences.
- Two first imports racing create one lineage.
- Two identical commits racing create one repository and one conflict.
- Forced duplicate `(lineage_id, sequence)` fails.
- Cross-owner composite membership fails.
- Cross-lineage latest pointer fails.
- Transaction rollback restores counter/latest.
- Account and repository cascades preserve other owners.

SQLite tests prove migration portability, constraint reflection, and serialized-writer behavior.
They **cannot prove PostgreSQL row-lock behavior, transaction isolation, partial-index semantics, or
concurrent create reconciliation**. Those concurrency cases and deferred cyclic FK/account-delete
cases must run against real PostgreSQL using separate connections and synchronization barriers—not
thread timing or sleeps.
