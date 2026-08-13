# RFC-0002 — Repository Lineage: Identity and Schema Design

| Field | Value |
| --- | --- |
| **RFC number** | RFC-0002 |
| **Title** | Repository Lineage: Identity and Schema Design |
| **Tracking issue** | [Second-Origin/PARTHA#298](https://github.com/Second-Origin/PARTHA/issues/298) |
| **Author** | @parthrohit22 |
| **Owner sign-off** | Confirmed |
| **Ratifier** | Pending — independent ratification by [@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24) is required before implementation begins (see [Q5](#q5-independent-ratification)); waived by owner, see [Ratification waiver (owner decision, 2026-08-11)](#ratification-waiver-owner-decision-2026-08-11) below |
| **Approval evidence** | Owner sign-off recorded directly against this design; no independent-maintainer ratification evidence exists yet; that ratification is itself waived by owner, see [Ratification waiver (owner decision, 2026-08-11)](#ratification-waiver-owner-decision-2026-08-11) below |
| **Created** | 2026-08-11 |
| **Last updated** | 2026-08-13 |
| **Status** | **Accepted** (owner-level design acceptance; see [§1.2](#12-what-accepted-does-and-does-not-mean-here) for what this does and does not authorize) |
| **Supersedes** | — |
| **Superseded by** | — |

> **This RFC records a design decision; it is not application code.** Acceptance does not by
> itself create the `repository_lineages` table, add columns to `repositories`, change
> `RepositoryService`, or alter any API or frontend surface. Implementation is tracked as a
> separate, explicitly blocked issue gated on [Q5](#q5-independent-ratification) — see
> [§1.2](#12-what-accepted-does-and-does-not-mean-here). See also
> [Ratification waiver (owner decision, 2026-08-11)](#ratification-waiver-owner-decision-2026-08-11) below.

---

## 1. Status and sign-off

### 1.1 Status

This RFC is **Accepted** at the owner level: @parthrohit22, the repository owner, has reviewed
and confirmed the design in [§4](#4-identity-design) through [§7](#7-product-direction-alignment) below,
including the resolution of all five open questions in [§10](#10-open-questions-and-resolutions).

### 1.2 What "Accepted" does and does not mean here

Following the ratification convention already established by
[RFC-0001 §1.2](REPOSITORY_INTELLIGENCE_V1_RFC.md#12-approval--ratification-rule), a design is
only cleared for **implementation** once an independent project maintainer other than the author
has ratified it. That independent ratification has **not** happened for this RFC: [Q5](#q5-independent-ratification)
explicitly requires @SHAURYAKSHARMA24 to independently ratify this design before any implementation
work starts. "Accepted" in the status table above therefore records that the owner has finished
shaping and approving the design — it does **not** clear the implementation gate. The companion
tracking issue for this RFC is documentation/design-only, and the implementation issue filed
alongside it is explicitly marked `[BLOCKED]` pending Q5. See
[Ratification waiver (owner decision, 2026-08-11)](#ratification-waiver-owner-decision-2026-08-11)
below, where the owner waives this gate.

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
| **Canonical branch** | The branch component of a lineage's join key, added by [Q1](#q1-branch-scoped-lineage). `NULL` under the same no-stable-identity rule as canonical source key. |
| **Standalone import** | A repository row that does not — and, under the rules in this RFC, cannot — auto-join any lineage. It is its own single-row lineage. |

## 3. Problem statement

`RepositoryRecord` (`apps/backend/app/models/repository.py`) currently identifies one imported
revision: a GitHub commit (`revision_kind="git"`, `revision_value=<sha>`) or an uploaded archive
(`revision_kind="upload"`, `revision_value=sha256:<hex>`), each addressed independently per
[RFC-0001 §3](REPOSITORY_INTELLIGENCE_V1_RFC.md#3-revision-and-snapshot-identity). `RepositoryService.import_github_repository`
and `import_uploaded_repository` (`apps/backend/app/services/repository_service.py`) dedupe on
`(owner_id, source_url, revision_value)` or `(owner_id, revision_value)` respectively — there is no
concept linking repeated imports of the same GitHub repository across different commits, or
representing "this is the third time this owner imported this repo" as a first-class relationship.

Two symptoms make this a real gap rather than a hypothetical one:

- The recently shipped dashboard "most recently analysed repository" surface
  (`feat/dashboard-latest-analysis-summary`, `apps/frontend/src/app/pages/DashboardPage.tsx`)
  computes "most recent" client-side, by reducing the flat repository list on `analysedAt`. It has
  no server-side concept of "the current head of this repository's history" to build on, and no way
  to group prior imports of the same repository together for that computation.
- [RFC-0001 §9 (Schema versioning)](REPOSITORY_INTELLIGENCE_V1_RFC.md#9-schema-versioning) and
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
`canonical_source_key` is derived by normalizing `source_url`: lowercased host and path, stripped
of a trailing `.git`, scheme, and trailing slash (e.g. `https://GitHub.com/Acme/Widgets.git` and
`git@github.com:Acme/Widgets.git` both normalize to `github.com/acme/widgets`). `canonical_branch`
is the resolved branch name from `revision_ref`, verbatim.

### 4.3 Uploads and unresolved-ref imports: standalone, no auto-join

Uploaded archives (`revision_kind="upload"`) have no source location to normalize — there is
nothing for `canonical_source_key` to key off. The same is true of a GitHub import whose
`revision_ref` did not resolve to a branch (a raw-SHA import with no branch context): there is a
source URL, but no stable branch component to complete the join key.

In both cases, `canonical_source_key` (and `canonical_branch`, once added — see [Q1](#q1-branch-scoped-lineage))
is `NULL`, and the row **does not auto-join any existing lineage**, even if another row with a
matching `source_url` exists. It is treated as a standalone, single-row lineage. This is a single
rule applied uniformly to both cases, not two separate rules — a repository row with no resolvable
stable identity never gets grouped automatically, regardless of why the identity is missing.

## 5. Schema proposal

### 5.1 New table `repository_lineages`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | String(36), PK | |
| `owner_id` | String, FK → `users.id`, indexed | |
| `canonical_source_key` | Text, nullable, indexed | See [§4.2](#42-canonical-source-key-derivation-github-imports) / [§4.3](#43-uploads-and-unresolved-ref-imports-standalone-no-auto-join) |
| `canonical_branch` | Text, nullable, indexed | Added by [Q1](#q1-branch-scoped-lineage); mirrors `canonical_source_key`'s NULL-for-no-stable-identity rule |
| `display_name` | Text | Inherited permanently from the first revision's `name` at lineage creation; see [Q4](#q4-display-name) |
| `latest_repository_id` | String(36), FK → `repositories.id`, nullable | Current head of the lineage; see [Q2](#q2-latest_repository_id-rollback) |
| `created_at` | DateTime | |

Constraint:

```sql
UNIQUE (owner_id, canonical_source_key, canonical_branch)
  WHERE canonical_source_key IS NOT NULL
```

The partial `WHERE` clause is required precisely because `canonical_source_key` (and
`canonical_branch`) are legitimately `NULL` for standalone rows ([§4.3](#43-uploads-and-unresolved-ref-imports-standalone-no-auto-join));
without it, every standalone row would collide on a `NULL = NULL` uniqueness check.

### 5.2 New columns on `repositories`

| Column | Type | Notes |
| --- | --- | --- |
| `lineage_id` | String(36), FK → `repository_lineages.id`, nullable, indexed | `NULL` for standalone rows |
| `sequence` | Integer, nullable | Monotonically increasing position within the lineage, assigned at import time; `NULL` for standalone rows |

No changes are proposed to `RepositoryRecord`'s existing identity columns
(`id`, `revision_kind`, `revision_value`, `revision_ref`) or to the existing
`uq_repositories_id_revision` constraint — revision identity per RFC-0001 is unaffected.

### 5.3 Concurrency: `sequence` assignment

This RFC proposes `sequence` as a monotonically increasing integer per lineage
([§5.2](#52-new-columns-on-repositories)) but does not specify the locking mechanism that
guarantees it stays gap-free and race-free under concurrent imports into the same lineage (e.g. two
`import_github_repository` calls resolving different commits of the same branch at the same time).
Candidate approaches — a `SELECT ... FOR UPDATE` on the parent `repository_lineages` row, a
database sequence/serial column, or an application-level advisory lock — are not evaluated here.
This is left as an implementation detail for the future migration PR, to be resolved when
`repository_lineages` and the backfill migration ([§6](#6-backfill-approach)) are actually built.

## 6. Backfill approach

Existing `repositories` rows predate `lineage_id`/`sequence` and must be backfilled by a single
migration, run once, forward-only (per the existing
[migration policy in RFC-0001 §10](REPOSITORY_INTELLIGENCE_V1_RFC.md#10-migration-policy)):

1. For every existing row with `source="github"` and a resolved `revision_ref`, compute
   `canonical_source_key` / `canonical_branch` per [§4.2](#42-canonical-source-key-derivation-github-imports)
   and group rows by `(owner_id, canonical_source_key, canonical_branch)`.
2. For each group, create one `repository_lineages` row. `display_name` is seeded from the
   **earliest** row's `name` in that group by `created_at` (per [Q4](#q4-display-name)).
   `sequence` is assigned per row by ascending `created_at` within the group.
   `latest_repository_id` is set to the row with the highest `sequence`.
3. Every row with `source="upload"`, or `source="github"` with no resolved `revision_ref`, is left
   with `lineage_id = NULL` and `sequence = NULL` — standalone, per [§4.3](#43-uploads-and-unresolved-ref-imports-standalone-no-auto-join).
   No synthetic lineage is created for these rows.
4. The backfill is idempotent and re-runnable: it is keyed off existing immutable columns
   (`owner_id`, `source_url`, `revision_ref`, `created_at`) and creates no data that isn't
   reproducible from current state.

This backfill is part of the scope gated on [Q5](#q5-independent-ratification) — it is design-only
in this RFC and is not implemented by this document. See
[Ratification waiver (owner decision, 2026-08-11)](#ratification-waiver-owner-decision-2026-08-11) below.

## 7. Product direction alignment

This design continues the project's stated priority of deepening the existing evidence and history
capability rather than adding new surfaces or languages: *"make history the moat"* — its first
increment is identity mapping, which is exactly what a lineage is — a stable cross-revision identity
for "the same repository over time," sitting below the fact-level identity mapping that priority is
ultimately for.

It also follows from a standing sequencing rule: *reliability before history* — graph evolution
requires deterministic snapshots and stable cross-revision identity, otherwise drift becomes noise.
Repository-level lineage identity is a prerequisite for that stable cross-revision identity, at a
level below the node/fact identity RFC-0001 §4 already governs.

This RFC explicitly does **not** propose graph diff, drift detection, or any consumer-facing
history feature — those remain future work, gated separately. It proposes only the identity and
schema layer those features would eventually sit on top of, consistent with the project's standing
instruction not to "finish the platform" ahead of demonstrated need.

## 8. Out of scope

- Any migration code, Alembic revision, or SQLAlchemy model change (see hard boundaries on the
  tracking issue and [§1.2](#12-what-accepted-does-and-does-not-mean-here)).
- Any change to `RepositoryService.import_github_repository` / `import_uploaded_repository`
  behavior, the dashboard "most recently analysed repository" feature, or any other application
  code.
- Any API contract or frontend surface change.
- Upload-to-lineage linking UX — deferred per [Q3](#q3-upload-linking).
- A rename/re-titling action for a lineage's `display_name` — deferred per [Q4](#q4-display-name).
- Cross-repository or cross-owner lineage matching. Lineage membership is always scoped to a single
  `owner_id`; this RFC does not propose any notion of shared or organization-wide lineage.

## 9. Alternatives rejected

- **Repository-scoped lineage key, ignoring branch** (`(owner_id, canonical_source_key)` only,
  branch-agnostic). Rejected by [Q1](#q1-branch-scoped-lineage): it would silently merge imports of
  different branches of the same repository into one lineage, which is a materially different
  identity claim than "the same branch over time" and would make any future diff/drift feature
  built on lineage produce misleading comparisons across unrelated branches.
- **Content-hash-based lineage matching for uploads** (attempt to match uploads into a lineage by
  fuzzy content similarity rather than requiring a stable source key). Rejected: this contradicts
  the project's standing anti-goal of a mutable "latest truth" in spirit — fuzzy matching would make
  lineage membership a heuristic, non-reproducible judgment rather than a deterministic identity
  rule. Uploads remain standalone per [§4.3](#43-uploads-and-unresolved-ref-imports-standalone-no-auto-join)
  until a future, explicit, user-driven linking action exists ([Q3](#q3-upload-linking)).
- **Automatic lineage-level rename when a revision's name changes.** Rejected by
  [Q4](#q4-display-name): a lineage's `display_name` permanently inherits the first revision's name
  instead, avoiding any implicit rename action with no user confirmation step.

## 10. Open questions and resolutions

All five open questions raised during design review are resolved as follows.

### Q1: Branch-scoped lineage

Key is `(owner_id, canonical_source_key, canonical_branch)`. New
`repository_lineages.canonical_branch` column (Text, nullable, indexed) added, mirroring
`canonical_source_key`'s NULL-for-no-stable-identity rule. Constraint becomes
`UNIQUE(owner_id, canonical_source_key, canonical_branch) WHERE canonical_source_key IS NOT NULL`.
A GitHub import with no resolved `revision_ref` (raw-SHA import, no branch context) does not
auto-join any lineage — standalone, same treatment as uploads ([§4.3](#43-uploads-and-unresolved-ref-imports-standalone-no-auto-join)).

### Q2: `latest_repository_id` rollback

`latest_repository_id` auto-rolls back to the next-highest `sequence` on revision deletion.

### Q3: Upload linking

Manual-only upload linking, deferred to a future feature.

### Q4: Display name

`display_name` permanently inherits the first revision's name — no rename action for now.

### Q5: Independent ratification

Requires independent ratification by [@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24)
before any implementation begins.

## 11. Sign-off

```text
Owner sign-off: confirmed
Open questions: 5/5 resolved
Tracking issue: Second-Origin/PARTHA#298
```

## Ratification waiver (owner decision, 2026-08-11)

Independent ratification by @SHAURYAKSHARMA24, as recommended in Q5, is waived by the owner.
Reasoning stated by the owner: sole-maintainer authority, plus the assessment that a review
conducted without the full context built up across this design's discussion would not be a
substantive independent check and risks being reviewed in name only.

This waiver does not resolve or retract Q5's underlying concern — it is a recorded acceptance of
that risk by the owner, not evidence the risk doesn't exist. The unresolved implementation-level
gap Q5 was partly meant to catch (the exact concurrency-locking mechanism for `sequence`
assignment, left as "an implementation detail for the future migration PR" in
[§5.3](#53-concurrency-sequence-assignment)) still applies and must be handled carefully in the
implementation PR precisely because no second reviewer will have checked it.

## 12. References

- [RFC-0001 — Repository Intelligence v1 Schema and Evidence Contract](REPOSITORY_INTELLIGENCE_V1_RFC.md)
- `apps/backend/app/models/repository.py` — `RepositoryRecord`
- `apps/backend/app/services/repository_service.py` — `RepositoryService.import_github_repository`, `import_uploaded_repository`
- `apps/frontend/src/app/pages/DashboardPage.tsx` — client-side "most recently analysed repository" computation (`feat/dashboard-latest-analysis-summary`)
