# RFC-0002 — Repository Lineage: Identity and Schema Design

| Field | Value |
| --- | --- |
| **RFC number** | RFC-0002 |
| **Title** | Repository Lineage: Identity and Schema Design |
| **Tracking issue** | [Second-Origin/PARTHA#298](https://github.com/Second-Origin/PARTHA/issues/298) |
| **Author** | @parthrohit22 |
| **Owner sign-off** | Confirmed |
| **Ratifier** | Independent ratification was waived by the owner on 2026-08-11; the implementation-critical amendment in [PR #328](https://github.com/Second-Origin/PARTHA/pull/328) was explicitly approved by the owner on 2026-08-19 |
| **Approval evidence** | Original owner sign-off is recorded below; the sequence, standalone-import, integrity, and deletion amendments were explicitly approved in [PR #328 review](https://github.com/Second-Origin/PARTHA/pull/328#pullrequestreview-4975035985) |
| **Created** | 2026-08-11 |
| **Last updated** | 2026-08-20 |
| **Status** | **Accepted; PR #328 amendment approved and #299 authorized for implementation** |
| **Supersedes** | — |
| **Superseded by** | — |

> **This RFC records a design decision; it is not application code.** Acceptance does not by
> itself create the `repository_lineages` table, add columns to `repositories`, change
> `RepositoryService`, or alter any API or frontend surface. Implementation is tracked as a
> separate issue, [#299](https://github.com/Second-Origin/PARTHA/issues/299). The exact authorization
> rule for that issue is recorded in [§1.2](#12-implementation-authorization).

---

## 1. Status and sign-off

### 1.1 Status

The baseline RFC was **Accepted** at the owner level: @parthrohit22 reviewed and confirmed its
identity design and the five questions in [§9](#9-open-questions-and-resolutions). PR #328 amends
that baseline with the implementation-critical sequence, integrity, standalone-import, deletion,
and migration contracts below. The owner explicitly approved those amendments on 2026-08-19 under
[§1.2](#12-implementation-authorization).

### 1.2 Implementation authorization

The independent-ratification condition originally recorded in [Q5](#q5-independent-ratification)
was waived by the owner on 2026-08-11. That waiver did not approve the implementation-critical
choices that were still absent from this RFC: durable sequence allocation, never-reused ordinals,
standalone-import storage semantics, and database-enforced membership integrity. PR #328 adds those
choices to the architecture contract and supplies the separately reviewed Alembic plan required by
#299. The owner explicitly approved them in
[PR #328 review](https://github.com/Second-Origin/PARTHA/pull/328#pullrequestreview-4975035985).

The authorization state is therefore explicit:

- **#299 AUTHORIZED FOR IMPLEMENTATION.** Implementation may be written and tested against this RFC
  and the reviewed migration plan.
- [#322](https://github.com/Second-Origin/PARTHA/issues/322) is a separate operational gate:
  repeatable migration rehearsal and rollback evidence are **required before the #299
  implementation PR merges**, but that gate does not prevent implementation work from proceeding.

The approval evidence is the owner review linked above. Approval authorizes writing and testing;
it does not mean #299 has been implemented or remove its operational pre-merge gate.

## 2. Terminology

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in this document are
to be interpreted as described in RFC 2119, consistent with the convention already established in
[RFC-0001 §2](REPOSITORY_INTELLIGENCE_V1_RFC.md#2-normative-terminology).

Domain terms used throughout this document:

| Term | Meaning |
| --- | --- |
| **Repository row** | A single `repositories` row (`RepositoryRecord`), i.e. one imported revision — one GitHub commit or one uploaded archive. Revision identity is already governed by [RFC-0001 §3](REPOSITORY_INTELLIGENCE_V1_RFC.md#3-revision-and-snapshot-identity); this RFC does not change it. |
| **Lineage** | A durable grouping of repository rows that represent successive imports of "the same repository" over time, from the same owner. A lineage has no revision content of its own — it is purely an identity/grouping record. |
| **Canonical source key** | A normalized, stable identifier derived from a GitHub import's source location, used to decide whether a new import joins an existing lineage. `NULL` when no such stable identity exists. |
| **Canonical branch** | The resolved ref component of a lineage's join key, added by [Q1](#q1-branch-scoped-lineage). It stores `revision_ref` verbatim and may therefore be a branch or tag; `NULL` under the same no-stable-identity rule as canonical source key. |
| **Unlineaged standalone import** | A repository row that does not auto-join a lineage. Its `lineage_id` and `sequence` are both `NULL`; no synthetic `repository_lineages` row exists for it. |

## 3. Problem statement

`RepositoryRecord` (`apps/backend/app/models/repository.py`) currently identifies one imported
revision: a GitHub commit (`revision_kind="git"`, `revision_value=<sha>`) or an uploaded archive
(`revision_kind="upload"`, `revision_value=sha256:<hex>`), each addressed independently per
[RFC-0001 §3](REPOSITORY_INTELLIGENCE_V1_RFC.md#3-revision-and-snapshot-identity). `RepositoryService.import_github_repository`
and `import_uploaded_repository` (`apps/backend/app/services/repository_service.py`) dedupe on
`(owner_id, source_url, revision_value)` or `(owner_id, revision_value)` respectively — there is no
concept linking repeated imports of the same GitHub repository across different commits, or
representing "this is the third time this owner imported this repo" as a first-class relationship.

The gap is material because a flat set of independent imported revisions has no durable,
owner-scoped identity for the logical repository those revisions came from. A consumer cannot
deterministically group successive imports or identify a current surviving member without that
separate identity.

[RFC-0001 §9 (Schema versioning)](REPOSITORY_INTELLIGENCE_V1_RFC.md#9-schema-versioning) and
  [§11 (Snapshot lifecycle)](REPOSITORY_INTELLIGENCE_V1_RFC.md#11-snapshot-lifecycle-and-immutability)
  already treat each revision's snapshot as immutable and independently addressable. Without a
  lineage concept sitting above that, any future cross-revision feature (diff, drift, "has this
  repository been re-analysed since I last looked") has no stable anchor to group revisions by.

This RFC proposes the identity rule and schema for that grouping, without changing revision
identity, snapshot immutability, or any existing API/frontend contract.

## 4. Identity design

### 4.1 Lineage key

A lineage is identified by the triple:

```text
(owner_id, canonical_source_key, canonical_branch)
```

Two repository rows belong to the same lineage if and only if they share the same `owner_id` and
both have a non-`NULL`, equal `canonical_source_key` and `canonical_branch`. This is the join key
`RepositoryService.import_github_repository` MUST use when deciding whether a new GitHub import
attaches to an existing lineage or starts a new one.

### 4.2 Canonical source key derivation (GitHub imports)

For a GitHub import with a resolved `revision_ref` (a named branch or tag the commit was resolved
from — see `RepositoryRecord.revision_ref`, `apps/backend/app/models/repository.py:44-46`),
`canonical_source_key` is derived by normalizing a source URL accepted by the import boundary:
lowercased host and owner/repository path, with scheme, trailing `.git`, and trailing slash removed
(for example, `https://github.com/Acme/Widgets.git` normalizes to
`github.com/acme/widgets`). #299 does not broaden the live importer beyond its currently accepted
public HTTPS GitHub URL grammar. The backfill may recognize strictly parsed historical HTTPS or SSH
GitHub repository forms as detailed in the migration plan; doing so does not expand live request
validation. Ambiguous values remain unlineaged.

`canonical_branch` stores the resolved `revision_ref` verbatim, including its `refs/heads/` or
`refs/tags/` prefix. Despite the retained field name, it is a normalized ref component and may
therefore identify a tag. The requested `branch` input is not lineage identity.

### 4.3 Uploads and unresolved-ref imports: unlineaged standalone imports

Uploaded archives (`revision_kind="upload"`) have no source location to normalize — there is
nothing for `canonical_source_key` to key off. The same is true of a GitHub import whose
`revision_ref` did not resolve to a branch (a raw-SHA import with no branch context): there is a
source URL, but no stable branch component to complete the join key.

In both cases the repository row has `lineage_id = NULL` and `sequence = NULL` and **no synthetic
lineage row is created**, even if another row has a matching `source_url`, upload hash, filename,
name, or similar tree. It is an **unlineaged standalone import**. This is one deterministic rule:
a repository row with no resolvable stable identity is never grouped automatically. Future manual
upload linking remains outside this RFC and must not be anticipated with heuristic grouping.

## 5. Schema proposal

### 5.1 New table `repository_lineages`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | String(36), PK | |
| `owner_id` | String(36), non-null, FK → `users.id`, indexed | `ON DELETE CASCADE` |
| `canonical_source_key` | Text, nullable, indexed | See [§4.2](#42-canonical-source-key-derivation-github-imports) / [§4.3](#43-uploads-and-unresolved-ref-imports-unlineaged-standalone-imports) |
| `canonical_branch` | Text, nullable, indexed | Added by [Q1](#q1-branch-scoped-lineage); mirrors `canonical_source_key`'s NULL-for-no-stable-identity rule |
| `display_name` | Text, non-null | Inherited permanently from the first revision's `name` at lineage creation; see [Q4](#q4-display-name) |
| `latest_repository_id` | String(36), nullable | Highest-sequence surviving member, or `NULL` for an empty lineage; membership is enforced by the composite constraint below |
| `next_sequence` | Integer, non-null | Next never-issued 1-based import ordinal; initialized to `1`, constrained to `>= 1`, incremented transactionally, and never decremented |
| `created_at` | timezone-aware DateTime, non-null | Earliest member time for backfill; current UTC for live creation |

Required constraints:

```sql
UNIQUE (owner_id, canonical_source_key, canonical_branch)
  WHERE canonical_source_key IS NOT NULL AND canonical_branch IS NOT NULL
```

- A check requires `canonical_source_key` and `canonical_branch` to be both `NULL` or both
  non-`NULL`. Null canonical fields are reserved for a possible future manually created lineage;
  #299 does not create a lineage for an unlineaged standalone import.
- `(id, owner_id)` is unique so repository membership can prove owner equality through a composite
  foreign key.
- `(latest_repository_id, id)` references `repositories(id, lineage_id)`, deferrable and initially
  deferred, so a non-null latest pointer must identify a repository in that exact lineage.

The partial unique key is also the authority when two transactions race to create the first
lineage for one canonical owner/source/ref identity.

### 5.2 New columns on `repositories`

| Column | Type | Notes |
| --- | --- | --- |
| `lineage_id` | String(36), nullable, indexed | `NULL` for unlineaged standalone imports; membership uses the composite owner constraint below |
| `sequence` | Integer, nullable | 1-based, never-reused import ordinal within the lineage; `NULL` for unlineaged standalone imports |

No changes are proposed to `RepositoryRecord`'s existing identity columns
(`id`, `revision_kind`, `revision_value`, `revision_ref`) or to the existing
`uq_repositories_id_revision` constraint — revision identity per RFC-0001 is unaffected.

The database MUST enforce all of these invariants:

- `lineage_id` and `sequence` are either both `NULL` or both non-`NULL`; a non-null sequence is at
  least `1`.
- `(lineage_id, sequence)` is unique. Gaps are permitted, but an ordinal cannot identify two
  repository rows in one lineage.
- `(id, lineage_id)` is unique as the target for the latest-member constraint.
- `(lineage_id, owner_id)` references `repository_lineages(id, owner_id)`, deferrable and initially
  deferred. A repository cannot join a lineage belonging to another owner.

The two composite foreign keys are architectural integrity requirements, not optional ORM checks.
Their deferral supports creating a lineage, attaching its first repository, and setting the latest
pointer—or moving that pointer before deletion—within one transaction. Both PostgreSQL and SQLite
migration paths MUST preserve and validate them.

### 5.3 Concurrency: `sequence` assignment

Sequence allocation is race-free and monotonically increasing. Previously issued sequence numbers
are never reused; gaps caused by deletion are valid. A sequence is an import ordinal, not commit
ancestry, commit time, analysis time, or proof that all lower ordinals still exist.

Each lineage owns durable allocation state in `next_sequence`. In the same database transaction
that creates the repository row, the importer atomically increments that lineage row and assigns
the previously unissued value. A rollback restores both the counter and repository/latest-pointer
changes. The unique `(lineage_id, sequence)` constraint remains defense in depth.

Concurrent first-lineage creation is reconciled through the owner-scoped canonical-key uniqueness
constraint: one insert wins, and the loser reloads that lineage and retries the database phase in a
bounded manner. On PostgreSQL, updating the lineage counter provides row-level serialization for
that lineage. SQLite uses its serialized writer behavior rather than pretending to provide
PostgreSQL row locks; its transaction, contention, retry, and constraint behavior MUST be validated
independently. The migration plan specifies the operational algorithm without changing this
contract.

### 5.4 Deletion semantics

Deleting a repository row never renumbers surviving members and never decrements `next_sequence`.
If the deleted row is `latest_repository_id`, the pointer moves in the same transaction to the
surviving member with the greatest sequence. If no member survives, the lineage row remains,
`latest_repository_id` becomes `NULL`, and `next_sequence` is preserved. A later import therefore
reuses the canonical lineage identity but never reuses an issued ordinal.

## 6. Backfill approach

Existing `repositories` rows predate `lineage_id`/`sequence` and must be backfilled by the
versioned Alembic migration sequence (per the existing
[migration policy in RFC-0001 §10](REPOSITORY_INTELLIGENCE_V1_RFC.md#10-migration-policy)):

1. For every existing row with `source="github"` and a resolved `revision_ref`, compute
   `canonical_source_key` / `canonical_branch` per [§4.2](#42-canonical-source-key-derivation-github-imports)
   and group rows by `(owner_id, canonical_source_key, canonical_branch)`.
2. For each group, create one `repository_lineages` row. `display_name` is seeded from the
   **earliest** row's `name` in that group by `(created_at, id)` (per
   [Q4](#q4-display-name)). `sequence` is assigned as `1..N` in that deterministic order.
   `latest_repository_id` is set to row `N` and `next_sequence` to `N + 1`.
3. Every row with `source="upload"`, or `source="github"` with no resolved `revision_ref`, is left
   with `lineage_id = NULL` and `sequence = NULL`—an unlineaged standalone import, per
   [§4.3](#43-uploads-and-unresolved-ref-imports-unlineaged-standalone-imports).
   No synthetic lineage is created for these rows.
4. The backfill uses deterministic lineage identifiers and explicit reconciliation/verification so
   an interrupted attempt can be inspected and safely rerun. It never guesses from ambiguous URLs
   or mutable display metadata.

This section defines the design-level outcome. Revision boundaries, DDL ordering, deterministic ID
construction, verification queries, interruption recovery, and downgrade mechanics belong to the
separately reviewed migration plan. #322 must supply the repeatable rehearsal and rollback evidence
before the #299 implementation PR merges.

## 7. Out of scope

- Any migration code, Alembic revision, or SQLAlchemy model change (see hard boundaries on the
  tracking issue and [§1.2](#12-implementation-authorization)).
- Any change to `RepositoryService.import_github_repository` / `import_uploaded_repository`
  behavior, the dashboard "most recently analysed repository" feature, or any other application
  code.
- Any API contract or frontend surface change.
- Upload-to-lineage linking UX — deferred per [Q3](#q3-upload-linking). Concurrent upload-hash
  deduplication is also outside #299 and is not solved by lineage allocation.
- A rename/re-titling action for a lineage's `display_name` — deferred per [Q4](#q4-display-name).
- Cross-repository or cross-owner lineage matching. Lineage membership is always scoped to a single
  `owner_id`; this RFC does not propose any notion of shared or organization-wide lineage.

## 8. Alternatives rejected

- **Repository-scoped lineage key, ignoring branch** (`(owner_id, canonical_source_key)` only,
  branch-agnostic). Rejected by [Q1](#q1-branch-scoped-lineage): it would silently merge imports of
  different branches of the same repository into one lineage, which is a materially different
  identity claim than "the same branch over time" and would make any future diff/drift feature
  built on lineage produce misleading comparisons across unrelated branches.
- **Content-hash-based lineage matching for uploads** (attempt to match uploads into a lineage by
  fuzzy content similarity rather than requiring a stable source key). Rejected: this contradicts
  the project's standing anti-goal of a mutable "latest truth" in spirit — fuzzy matching would make
  lineage membership a heuristic, non-reproducible judgment rather than a deterministic identity
  rule. Uploads remain unlineaged standalone imports per
  [§4.3](#43-uploads-and-unresolved-ref-imports-unlineaged-standalone-imports)
  until a future, explicit, user-driven linking action exists ([Q3](#q3-upload-linking)).
- **Automatic lineage-level rename when a revision's name changes.** Rejected by
  [Q4](#q4-display-name): a lineage's `display_name` permanently inherits the first revision's name
  instead, avoiding any implicit rename action with no user confirmation step.

## 9. Open questions and resolutions

All five open questions raised during design review are resolved as follows.

### Q1: Branch-scoped lineage

Key is `(owner_id, canonical_source_key, canonical_branch)`. New
`repository_lineages.canonical_branch` column (Text, nullable, indexed) added, mirroring
`canonical_source_key`'s NULL-for-no-stable-identity rule. A pair check requires both fields to be
null or non-null together. The constraint becomes `UNIQUE(owner_id, canonical_source_key,
canonical_branch) WHERE canonical_source_key IS NOT NULL AND canonical_branch IS NOT NULL`.
A GitHub import with no resolved `revision_ref` (raw-SHA import, no branch context) does not
auto-join any lineage—an unlineaged standalone import, the same treatment as uploads
([§4.3](#43-uploads-and-unresolved-ref-imports-unlineaged-standalone-imports)).

### Q2: `latest_repository_id` rollback

`latest_repository_id` moves to the highest surviving sequence on revision deletion. Deleting the
final member preserves the empty lineage with a null latest pointer and unchanged `next_sequence`.

### Q3: Upload linking

Manual-only upload linking, deferred to a future feature.

### Q4: Display name

`display_name` permanently inherits the first revision's name — no rename action for now.

### Q5: Independent ratification

Independent ratification by [@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24) was requested
before implementation and waived by the owner on 2026-08-11. The implementation-critical
amendment in PR #328 instead received explicit owner approval under
[§1.2](#12-implementation-authorization).

## 10. Sign-off

```text
Owner sign-off: confirmed
Open questions: 5/5 resolved
Tracking issue: Second-Origin/PARTHA#298
PR #328 architecture amendment: explicitly approved by owner on 2026-08-19
#299 implementation: authorized for writing and testing; not yet implemented
#322 operational evidence: required before the #299 implementation PR merges
```

## Ratification waiver (owner decision, 2026-08-11)

Independent ratification by @SHAURYAKSHARMA24, as recommended in Q5, is waived by the owner.
Reasoning stated by the owner: sole-maintainer authority, plus the assessment that a review
conducted without the full context built up across this design's discussion would not be a
substantive independent check and risks being reviewed in name only.

This waiver did not resolve or retract Q5's underlying concern—it recorded acceptance of the
ratification risk, not evidence that the sequence design was complete. The PR #328 amendment now
resolves that design gap normatively in [§5.3](#53-concurrency-sequence-assignment) with durable
per-lineage allocation state, transaction semantics, canonical-key race reconciliation, and
database uniqueness. The explicit owner approval recorded under
[§1.2](#12-implementation-authorization) on 2026-08-19 authorized those additions.

## 11. References

- [RFC-0001 — Repository Intelligence v1 Schema and Evidence Contract](REPOSITORY_INTELLIGENCE_V1_RFC.md)
- `apps/backend/app/models/repository.py` — `RepositoryRecord`
- `apps/backend/app/services/repository_service.py` — `RepositoryService.import_github_repository`, `import_uploaded_repository`
- `apps/frontend/src/app/pages/DashboardPage.tsx` — client-side "most recently analysed repository" computation (`feat/dashboard-latest-analysis-summary`)
