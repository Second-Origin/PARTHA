# RFC-0001 — Repository Intelligence v1 Schema and Evidence Contract

| Field | Value |
| --- | --- |
| **RFC number** | RFC-0001 |
| **Title** | Repository Intelligence v1 Schema and Evidence Contract |
| **Tracking issue** | [Second-Origin/PARTHA#86](https://github.com/Second-Origin/PARTHA/issues/86) |
| **Accepted schema version** | `ri.v1` |
| **Author** | @parthrohit22 |
| **Ratifier** | [@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24), an independent project maintainer other than the author |
| **Approval evidence** | [Issue #86 approval comment](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780) and [PR #101 approval review](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647) |
| **Approval / ratification date** | 2026-07-16 |
| **Created** | 2026-07-15 |
| **Last updated** | 2026-07-16 |
| **Status** | **Accepted** |
| **Supersedes** | — |
| **Superseded by** | — |

> **This RFC records the accepted architectural contract; it is not application code.** Acceptance
> does not by itself implement snapshots, persistence, extractors, resolvers, queries, jobs,
> migrations, or consumer migration. Downstream implementation is tracked in issues
> [#87–#95](https://github.com/Second-Origin/PARTHA/issues/87); see
> [§16, Dependency gate](#16-dependency-gate) and [§17, implementation status](#17-current-behavior-vs-accepted-contract-vs-implementation-status).

---

## 1. Status and approval

### 1.1 Status

This RFC is **Accepted**. Independent project maintainer
[@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24) recorded approval in the
[Issue #86 approval comment](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780)
and the [PR #101 approval review](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647)
on 2026-07-16. This final pre-merge update records that decision in the RFC; merging PR #101 makes
the accepted record authoritative on `dev` and closes #86.

### 1.2 Approval / ratification rule

- **Ratification requires an independent project maintainer other than the author.** The author
  (@parthrohit22) cannot ratify their own RFC, and per [CONTRIBUTING §6](../../CONTRIBUTING.md) must
  not self-merge. A reviewer's `write` access alone does not make them a maintainer; ratification
  authority must be an actual project maintainer.
- **Approval does not automatically edit this document.** After approval is recorded, a **final
  pre-merge update MUST**:
  1. set `Status: Accepted`;
  2. record the ratifier (the approving maintainer) and the approval date;
  3. change the pull request description from `Related to #86` to `Closes #86`.
  This update fulfills all three requirements using the recorded
  [Issue #86 approval](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780)
  and [PR #101 approval](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647).
  Merge of this updated document makes the accepted contract authoritative; the status change is
  made by hand in this pre-merge update, not inferred from the merge event.
- The author **MUST NOT** self-declare this RFC approved and **MUST NOT** set `Status: Accepted`
  without a recorded independent-maintainer approval.
- Amendments after acceptance follow the schema-versioning rules in [§9](#9-schema-versioning): a
  backward-compatible clarification amends this document in place; a breaking change is a new RFC
  that proposes `ri.v2` for ratification.

### 1.3 What approval unblocks

The recorded approval satisfies the governance dependency gate in [§16](#16-dependency-gate).
After PR #101 merges, downstream issues may proceed against the authoritative accepted contract,
subject to their own dependencies and review requirements. Acceptance does not mark any downstream
capability as implemented or as current product behavior.

### 1.4 Ratification follow-up

The original proposal was merged in [PR #99](https://github.com/Second-Origin/PARTHA/pull/99)
without the independent-maintainer approval and final status update required by §1.2. Tracking
issue [#86](https://github.com/Second-Origin/PARTHA/issues/86) was reopened on 2026-07-16 so that
the missing ratification step can be completed explicitly rather than inferred from the earlier
merge.

Independent project maintainer @SHAURYAKSHARMA24 subsequently recorded approval in both
[Issue #86](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780) and
[PR #101](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647). This final
pre-merge update sets the status to **Accepted**, records the ratifier and date, and uses the
`Closes #86` form in PR #101. It resolves the governance gap left by PR #99. A maintainer other
than the author must merge PR #101 for this accepted record to become authoritative and for #86
to close.

---

## 2. Normative terminology

### 2.1 Requirement levels

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as follows,
consistent with RFC 2119 / RFC 8174 and with the existing convention in
[CONTRIBUTING §Preamble](../../CONTRIBUTING.md):

- **MUST** / **REQUIRED** / **SHALL** — an absolute requirement. A conforming implementation that
  violates a MUST is non-conforming and the corresponding pull request must be rejected.
- **MUST NOT** / **SHALL NOT** — an absolute prohibition.
- **SHOULD** / **RECOMMENDED** — a strong expectation. Deviation requires a documented reason on
  the implementing issue and reviewer agreement.
- **MAY** / **OPTIONAL** — genuinely discretionary; either choice conforms.

### 2.2 Defined terms

These terms have exactly the meaning below throughout the intelligence track. They refine the
informal usage in [REPOSITORY_INTELLIGENCE.md](REPOSITORY_INTELLIGENCE.md); where the two differ,
this RFC governs for `ri.v1` artifacts.

| Term | Definition |
| --- | --- |
| **Snapshot** | An immutable, sealed set of facts about **one repository at one exact revision**, produced under one schema version and one predeclared producer-version set. The unit of reproducibility. |
| **Fact** | A single stored claim in a snapshot. Every fact is a **node**, **edge**, or **assertion**, carries a **truth class** ([§7](#7-truth-classes)), and — when its truth class requires it — carries provenance or derivation references ([§6](#6-provenance-contract)). |
| **Node** | A fact asserting the existence of an entity: a repository, module, file, symbol, or dependency. Identified by a **stable key** ([§4](#4-node-identity-and-stable-keys)). |
| **Edge** | A fact asserting a directed relationship between two nodes: `subject —predicate→ object` ([§5](#5-edgefact-identity)). |
| **Assertion** | A separate fact that assigns a derived property/value to an existing node without duplicating or mutating that entity node. `ri.v1` assertions are inferred and have deterministic identities ([§5.6](#56-inferred-property-assertions)). |
| **Observation** | A stored, evidence-bearing extractor record for one exact syntactic occurrence. It is provenance input to resolution/inference, not a graph node or edge ([§6.4](#64-observations-and-the-derived_from-reference-model)). |
| **Evidence** | A single provenance record ([§6](#6-provenance-contract)) that ties a fact to an exact source location (path + line span) in the snapshot's stored revision, plus the extractor/resolver that produced it. |
| **Provenance** | The complete set of evidence attached to a fact — *where the fact came from and how it was derived*. A fact may carry one or more evidence records. |
| **Diagnostic** | A structured record of something the pipeline could not turn into a fact, or could turn into a fact only with a caveat: an unsupported construct, an ambiguous resolution, a parse failure, an invalid span, a collision, a skipped input. Diagnostics are first-class snapshot output ([§8](#8-diagnostics-model)). |
| **Extractor** | A component that reads source at a byte/AST level and emits **observed** facts with exact spans. Named and versioned (e.g. `typescript-ast@1.0.0`). |
| **Resolver** | A component that consumes stored extractor output and emits **resolved** facts via a documented, deterministic algorithm ([§7](#7-truth-classes)). Named and versioned. It does not read the working tree. |
| **Producer** | Any versioned component enabled in the planned snapshot pipeline that can emit snapshot nodes, edges, assertions, observations, or diagnostics: extractors, resolvers, classifiers, and inference producers. Narrative generators are consumers and are not snapshot producers. |
| **Schema version** | The version of *this contract* — node/edge shape, stable-key format, provenance record, truth classes, canonicalization. Value for this RFC: `ri.v1` ([§9](#9-schema-versioning)). |
| **Producer version** | The independently incremented version of a producer implementation. Distinct from schema version ([§9.4](#94-schema-version-vs-producer-version)). |

---

## 3. Revision and snapshot identity

### 3.1 Problem this settles

Before #87, revision identity was coarse and mutable: `RepositoryService._metadata_with_intelligence`
stashed a `commitSha` inside the mutable `repo_metadata` JSON blob. A value inside a mutable blob is
not an identity — it cannot be indexed, uniquely constrained, made immutable, or joined against a
snapshot table. #87 now makes the identity in this section first-class; #88 keys normalized snapshots
to it. The legacy description remains relevant to rows created before the migration.

### 3.2 Revision identity

A **revision** is the exact version of source a snapshot describes. There are exactly two kinds in
`ri.v1`:

```jsonc
{ "kind": "git",    "value": "<40-lowercase-hex-commit-sha>", "ref": "refs/heads/main" }
{ "kind": "upload", "value": "sha256:<64-lowercase-hex>",     "ref": null }
```

- **Git identity (`kind: "git"`).** `value` MUST be the immutable **40-character lowercase
  hexadecimal commit SHA** (SHA-1 object name), as already read by
  [`GitHubClient.read_head_commit`](../../apps/backend/app/github/client.py#L45) via
  `git rev-parse HEAD`. `ref` MUST additionally record the **resolved ref** the import targeted
  (e.g. `refs/heads/main`), derived from the requested branch. When SHA-256 object-format
  repositories are supported, a 64-character SHA is permitted and the hash algorithm is recorded;
  `ri.v1` targets the SHA-1 default that `git` produces today.
- **Upload identity (`kind: "upload"`).** `value` MUST be the stable **`sha256:` content hash** of
  the uploaded archive, exactly as already computed by
  [`_content_hash_for_upload`](../../apps/backend/app/services/repository_service.py#L284). Uploads
  have no git history; the content hash is the revision.
- **Moving names are metadata, never identity.** A branch name (`main`), a tag, or `HEAD` is a
  *moving pointer*. It MAY be stored as descriptive metadata (`ref`, `branch`) but MUST NOT be used
  as, or as part of, revision identity. Two snapshots of `main` taken a week apart are different
  revisions.

`value` is REQUIRED and immutable once written. It MUST be an indexed column (#87), not a JSON-blob
field.

### 3.3 Snapshot identity

A snapshot's identity is the composite:

```text
(repository_id, revision.value, schema_version, producer_version_set, config_hash)
```

- `repository_id` — the owning repository (`repo_…`), scoping the snapshot to one owner's repository.
- `revision.value` — the exact revision ([§3.2](#32-revision-identity)).
- `schema_version` — e.g. `ri.v1` ([§9](#9-schema-versioning)).
- `producer_version_set` — the lexicographically sorted, deduplicated set of every **enabled**
  extractor, resolver, classifier, and inference producer in the planned pipeline, each encoded as
  `producer@version` (for example
  `["architecture-classifier@1.0.0", "import-resolver@1.0.0", "python-ast@1.0.0", "reference-resolver@1.0.0", "repository-inventory@1.0.0", "route-resolver@1.0.0", "typescript-ast@1.0.0"]`).
  It describes the pipeline that is about to run, not only components that later happen to emit
  output.
- `config_hash` — the deterministic hash of the output-affecting analysis configuration, computed
  exactly as defined in [§12.7](#127-config_hash). Configuration that cannot change graph output
  MUST NOT be included.

These five components are the **semantic identity components** of a snapshot. A new snapshot is
required if and only if at least one of them changes.

**The complete semantic identity MUST be computable before an analysis job is enqueued.** Pipeline
planning resolves every enabled producer and version, canonicalizes `producer_version_set`, computes
`config_hash`, and performs sealed-snapshot lookup before extraction begins. Any producer
implementation-version change therefore changes identity and cannot accidentally reuse a snapshot
built by different code. An implementation MAY record a lexicographically sorted, deduplicated
`actual_producers` field after execution for operational auditing, but that field MUST NOT replace
the planned `producer_version_set`, alter semantic identity, or be used for pre-enqueue lookup.

Each snapshot ALSO carries an opaque surrogate `snapshot_id` (`snap_…`) as its primary key. The
surrogate is for referencing; the composite above is the **semantic** identity and MUST be enforced
by a uniqueness constraint that permits **at most one sealed snapshot** per composite identity (#88).

### 3.4 Reanalysis, reuse, and idempotency

These rules are normative and are stated identically in [§11.3](#113-immutability),
[§11.4](#114-failed-extraction-cancellation-retry-93-interaction), and
[§11.5](#115-concurrency-and-idempotency); they must not be contradicted anywhere in this document:

- **Identical composite identity MUST reuse the existing sealed snapshot.** If a **sealed** snapshot
  already exists for the exact composite identity in [§3.3](#33-snapshot-identity), an analysis
  request with that identity **MUST** return the existing sealed snapshot. It **MUST NOT** build a
  second one. (Because the canonical graph hash — [§12](#12-canonical-graph-hash) — is deterministic
  for identical inputs, a rebuild could only reproduce the same bytes; reuse is therefore required,
  not merely permitted.)
- **A new snapshot is required only when a semantic identity component changes.** If *any* component
  of the composite differs — a new revision, a changed planned producer version, a schema bump, or
  a `config_hash` change — the result is a **distinct** snapshot. Otherwise no new snapshot is
  produced.
- **Concurrent identical requests MUST coordinate so that at most one build seals.** When two
  requests race for the same composite identity, implementations MUST ensure at most one `building`
  attempt reaches `completed`; after one seals, the others reuse it. The uniqueness constraint on
  sealed snapshots ([§3.3](#33-snapshot-identity)) is the backstop.
- **Retries may create separate `building` or `failed` attempts, but only one snapshot may become
  sealed** for a given composite identity ([§11.4](#114-failed-extraction-cancellation-retry-93-interaction)).
- **Completed snapshots remain immutable and are never rewritten** ([§11.3](#113-immutability)).
  Corrections come from a *new* snapshot produced by changed inputs, never from editing a sealed one.

### 3.5 Migration of the existing `commitSha` (handled by #87)

The existing `repo_metadata["commitSha"]` value is migrated forward, not dropped:

- #87 adds first-class, indexed, immutable revision columns to the repository record
  ([`repository.py`](../../apps/backend/app/models/repository.py)): the git commit SHA **and** the
  resolved ref for git imports, and the `sha256:` content hash for uploads.
- The Alembic migration backfills those columns from the existing `repo_metadata["commitSha"]`
  values (a git SHA, or a `sha256:` upload hash), per [CONTRIBUTING §10](../../CONTRIBUTING.md).
- Once the column is authoritative, the `commitSha` stash in `_metadata_with_intelligence` is
  removed (#87 acceptance criterion). The migration MUST downgrade cleanly.
- This is a *transformation* of an existing value into a typed column, not a re-derivation — see
  [§10](#10-migration-policy) for the distinction between transformation and re-extraction, which
  governs the graph facts themselves.

---

## 4. Node identity and stable keys

### 4.1 Principle and cross-revision guarantees

Every node has a **deterministic stable key**: a pure function of the repository-relative source
location and the node's semantic name, containing no random component, no timestamp, and no
autoincrement id. Stable keys are UTF-8 strings; the general grammar is `<kind-prefix>:<body>`.

Node stable keys are unique **within a snapshot**. Persistence MUST enforce
`UNIQUE(snapshot_id, stable_key)`, so each entity has exactly one node record in a snapshot. Entity
existence nodes are `observed`; a resolver or classifier MUST NOT create a second node with the same
key or change the existing node's truth class. Derived properties belong in assertions
([§5.6](#56-inferred-property-assertions)).

`ri.v1` makes exactly two levels of guarantee, and they must not be conflated:

- **Within a revision (strong, MUST).** For a **fixed stored revision and schema version**, the same
  entity MUST always receive the same stable key. Stable keys are fully deterministic per revision —
  this is what #88's storage, #92's queries, and #94's determinism check rely on.
- **Across revisions (qualified).** A stable key identifies "the same entity" across two revisions
  **only to the extent its inputs are unchanged.** Concretely:
  - **Ordinary, non-colliding named symbols are comparable across revisions.** A symbol whose
    `<file-path>::<qualified-name>` is unique in its file carries **no** discriminator, so its key
    depends only on its file path and qualified name. As long as neither changes, the key is identical
    across revisions and a consumer MAY treat two snapshots' facts with that key as the same entity.
    A file rename or a rename of any enclosing scope changes the key — that is a *different identity*,
    correctly, because the source location changed.
  - **Duplicate-symbol and anonymous-symbol ordinals are revision-local.** The `#<n>` overload
    discriminator ([§4.3](#43-canonical-stable-key-formats)) and the `(anonymous:<kind>#<ordinal>)`
    segment are assigned by **source order within the revision**. Inserting or deleting an earlier
    occurrence renumbers the later ones, so these keys **MUST NOT** be assumed to identify the same
    entity across revisions. They are stable *within* a revision and are for intra-snapshot reference
    and hashing only; cross-revision matching of duplicate/anonymous symbols is explicitly **not
    guaranteed** in `ri.v1`. A consumer that needs to track such a symbol across revisions MUST fall
    back to evidence (path + span) comparison, not the ordinal key.
  - **`repository`, `module`, `file`, and `dependency` keys are cross-revision stable** as long as
    their path/name inputs are unchanged (they carry no ordinal). The repository-root key is the
    constant `repo:root`, scoped by its snapshot rather than by a database identifier.

This is the honest limit of `ri.v1`: source-order ordinals buy determinism cheaply but cannot promise
cross-revision identity for the entities that need them. See
[§15.1](#151-operational-costs-and-limitations-stated-honestly) for the consequence and the deferred
alternative (a content-based semantic discriminator) considered for a future schema version.

### 4.2 Path normalization (applies to every path in a stable key or evidence record)

A **repository-relative POSIX path** is produced by this exact procedure; it is normative for
stable keys ([§4](#4-node-identity-and-stable-keys)) and for evidence paths ([§6](#6-provenance-contract)):

1. Interpret the path relative to the repository root (the analyzed root, after
   [`_resolve_repository_root`](../../apps/backend/app/services/repository_service.py#L259)).
2. Convert all backslashes to forward slashes (`/`). POSIX separator only.
3. Split on `/`, resolve `.` segments (drop them) and `..` segments (pop the previous segment)
   **lexically, without touching the filesystem**.
4. **Reject** any path that, after lexical resolution, escapes the repository root (a leading `..`
   that cannot be popped). Such a path MUST NOT produce a node; it produces an
   `RI-SEC-PATH-ESCAPE` diagnostic ([§8](#8-diagnostics-model)) and is dropped.
5. **Reject** absolute paths and paths that traverse a **symlink that escapes the repository**;
   emit `RI-SEC-PATH-ESCAPE`. Symlinks that stay within the repository are followed to their
   normalized in-repo target.
6. Strip any leading `/`. The result has no leading slash, no `.`/`..` segments, and uses `/`.
7. **No leading `./`.** `.` alone (the repository root itself) is represented as the empty string
   for the repository node's path and as the literal path for the module rooted there.
8. **Case sensitivity.** Paths are compared **case-sensitively** and byte-exactly as normalized in
   step 9. This matches git's default index behavior; a case-only rename is a distinct path. On a
   case-insensitive host filesystem, two paths differing only in case that collide MUST emit
   `RI-KEY-COLLISION` rather than silently merging.
9. **Unicode.** Path strings are normalized to **Unicode NFC** before use in a key. Two paths that
   are canonically equivalent under NFC are the same path; if the stored revision contains both an
   NFC and a non-NFC spelling of the same name, that is a collision and emits `RI-KEY-COLLISION`.

### 4.3 Canonical stable-key formats

| Node kind | Prefix | Body | Example |
| --- | --- | --- | --- |
| **repository** | `repo` | the constant repository-root token `root` | `repo:root` |
| **module** | `mod` | normalized repo-relative POSIX **directory** path (empty string = repository root) | `mod:src/auth` |
| **file** | `file` | normalized repo-relative POSIX **file** path | `file:src/auth/service.ts` |
| **symbol** | *(none)* | `<file-path>::<qualified-name>[#<discriminator>]` | `src/auth/service.ts::AuthService.login` |
| **dependency** | `dep` | `<ecosystem>:<name>` | `dep:npm:react`, `dep:pypi:fastapi` |

Notes and rules:

- **Repository root.** Every snapshot has exactly one repository entity node, `repo:root`. The
  opaque `repository_id` remains part of snapshot ownership and semantic identity ([§3.3](#33-snapshot-identity))
  but MUST NOT appear in any node stable key. This prevents a generated database UUID from entering
  canonical graph content. Re-imports of the same source can therefore produce comparable graph
  content even when their repository records differ.
- The **symbol** key deliberately uses the `<file-path>::<qualified-name>` form shown in the issue's
  target contract, with **no `sym:` prefix**, so it reads naturally in evidence and query output.
  Consumers detect a symbol key by the presence of `::`.
- **Qualified name.** The dotted path of enclosing named scopes from file top-level to the symbol,
  joined by `.`. TypeScript: `Namespace.Class.method`. Python: `module-is-the-file`, so
  `OuterClass.inner_method`, `outer_func.nested_func`. The qualified name is **language-native
  dotted notation**, not a file path.
- **Nested symbols** append each enclosing scope: `service.ts::AuthService.Session.refresh`.
- **Overloads / duplicate names.** When two symbols in one file share an identical
  `<file-path>::<qualified-name>` (TypeScript function overloads, two `def foo` at the same scope, a
  re-`class` after conditional definition), each after the first receives a **`#<n>` discriminator**
  assigned by **ascending source start position** (`#2`, `#3`, …); the first occurrence has **no**
  discriminator. This is deterministic given a fixed revision. The collision itself is also recorded
  as an `RI-KEY-DUP-SYMBOL` diagnostic (informational) so consumers can surface it.
  **Cross-revision caveat:** the `#<n>` ordinal is **revision-local** — inserting or deleting an
  earlier occurrence renumbers later ones — so a `#<n>` key MUST NOT be assumed to identify the same
  entity across revisions ([§4.1](#41-principle-and-cross-revision-guarantees)).
- **Anonymous / generated symbols.** A symbol with no source name that must be represented (an
  exported default arrow function, an anonymous class expression) gets a **synthetic qualified
  segment** of the form `(anonymous:<kind>#<ordinal>)` where `<ordinal>` is its 1-based position
  among anonymous symbols **within the same enclosing scope**, by source order. Example:
  `routes.ts::(anonymous:arrow#1)`. Synthetic segments are the only place parentheses appear in a
  qualified name, which keeps them unambiguous against real identifiers. Like the `#<n>` overload
  ordinal, the anonymous `#<ordinal>` is **revision-local** and MUST NOT be used for cross-revision
  identity ([§4.1](#41-principle-and-cross-revision-guarantees)).
- **Language namespace.** Language is **not** part of the stable key: the file extension already
  disambiguates same-named symbols across languages, and a symbol key is always scoped to exactly
  one file. Language is stored as a **node property**. For **dependencies**, the `ecosystem`
  segment (`npm`, `pypi`) *is* the namespace and is REQUIRED, because the same package name can
  exist in multiple ecosystems.
- **External dependencies.** A dependency the repository declares but does not contain is a
  `dep:<ecosystem>:<name>` node with truth class `observed` (the declaration is observed in a
  manifest). Its `name` is the manifest-declared package name, lowercased only where the ecosystem
  is case-insensitive (npm: preserve; PyPI: normalize per PEP 503 — lowercase, runs of `._-` → `-`).
- **Collision detection.** If two *distinct* entities would receive the **same** stable key and the
  `#<n>` discriminator rule does not apply (i.e. they are genuinely different kinds, or a path
  collision from [§4.2](#42-path-normalization-applies-to-every-path-in-a-stable-key-or-evidence-record)),
  the pipeline MUST emit an `RI-KEY-COLLISION` diagnostic and MUST NOT silently overwrite one with
  the other. Collision handling is a snapshot-completing diagnostic (visible gap), not a fatal
  error, unless it prevents a coherent graph ([§8.4](#84-which-diagnostics-fail-a-snapshot)).

### 4.4 Valid and invalid examples

#### TypeScript — valid

| Source (`src/auth/service.ts`) | Stable key |
| --- | --- |
| `export class AuthService { login() {} }` | `src/auth/service.ts::AuthService.login` |
| `export function issueToken() {}` (in `src/auth/tokens.ts`) | `src/auth/tokens.ts::issueToken` |
| second `export function fmt(x): string;` overload | `src/auth/util.ts::fmt#2` |
| `export default () => {}` | `src/auth/handler.ts::(anonymous:arrow#1)` |
| `import react` (declared in `package.json`) | `dep:npm:react` |

#### TypeScript — invalid (rejected, produces a diagnostic, no node)

| Attempted | Why rejected |
| --- | --- |
| `file:../secrets/.env` | escapes repo root → `RI-SEC-PATH-ESCAPE` |
| `file:/etc/passwd` | absolute path → `RI-SEC-PATH-ESCAPE` |
| `file:src\auth\service.ts` (unnormalized backslashes) | must be normalized to `src/auth/service.ts` before use; raw form is invalid |
| `src/auth/service.ts::login` for a method of `AuthService` | missing enclosing scope; qualified name MUST be `AuthService.login` |

#### Python — valid

| Source (`app/api/routes/auth.py`) | Stable key |
| --- | --- |
| `class AuthController:` → `def login(self):` | `app/api/routes/auth.py::AuthController.login` |
| top-level `def get_current_user():` | `app/api/routes/auth.py::get_current_user` |
| second `def handler` at module scope | `app/api/routes/auth.py::handler#2` |
| `import fastapi` (declared in `pyproject.toml`) | `dep:pypi:fastapi` |
| nested `def _inner()` inside `def outer()` | `app/api/routes/auth.py::outer._inner` |

#### Python — invalid

| Attempted | Why rejected |
| --- | --- |
| `dep:pypi:Flask` | PyPI names are PEP 503-normalized → `dep:pypi:flask` |
| `file:app/../../etc/hosts` | escapes repo root → `RI-SEC-PATH-ESCAPE` |
| symbol key using `/` instead of `.` in qualified name (`auth.py::AuthController/login`) | qualified name uses language-native `.` |

---

## 5. Edge/fact identity

### 5.1 Canonical predicates

These are the **initial registered `ri.v1` predicate set** (lowercase `snake_case`). The set is
**not permanently closed**: adding a new predicate with new semantics is a **compatible `ri.v1`
addition** ([§9.1](#91-compatible-additions)), and conforming readers MUST ignore or safely preserve
predicates they do not recognize ([§9.1](#91-compatible-additions)). **Removing, renaming, or
changing the meaning of** an existing predicate is a breaking change that requires `ri.v2`
([§9.2](#92-breaking-changes-require-riv2)).

| Predicate | Meaning | Typical subject → object | Required by |
| --- | --- | --- | --- |
| `contains` | structural containment | repository→module, module→file, file→symbol | #88, #91 |
| `defines` | a file/scope defines a symbol | file→symbol, symbol→symbol (nested) | #89, #90, #91 |
| `imports` | an import statement references a module/dependency | file→file, file→dependency | #89, #90, #91 |
| `calls` | a call site invokes a callable | symbol→symbol | #91 |
| `routes_to` | an HTTP route declaration maps to a handler | symbol(route)→symbol(handler) | #90, #91, #95 |
| `depends_on` | repository depends on an external dependency | repository→dependency | #91 |
| `implements` | a type implements/realizes an interface/protocol | symbol→symbol | #91 |

> Note: today's `RelationshipType` union, consumed by `KnowledgeGraphRelationship`
> ([`models.py:25`](../../apps/backend/app/intelligence/models.py#L25)), also lists `extends`,
> `references`, and `exports`, of which only four are ever emitted
> ([REPOSITORY_INTELLIGENCE.md](REPOSITORY_INTELLIGENCE.md)). `ri.v1` starts from the registered set
> above; `extends` folds into `implements`-adjacent modeling for v1 and `exports`/`references` are
> represented via `defines` + node properties. Reviving them later is a compatible `ri.v1` addition
> when a resolver actually produces them, not an `ri.v2` change.

### 5.2 Subject and object identity

The `subject` and `object` of every edge are **node stable keys** ([§4](#4-node-identity-and-stable-keys)),
each carried with its `kind`:

```json
{
  "subject": { "kind": "symbol", "stable_key": "src/auth/service.ts::AuthService.login" },
  "predicate": "calls",
  "object": { "kind": "symbol", "stable_key": "src/auth/tokens.ts::issueToken" }
}
```

An edge MUST NOT reference a node that does not exist in the same snapshot. This includes external
dependencies: a `file → dependency` or `repo:root → dependency` edge requires the corresponding
`dep:<ecosystem>:<name>` node. An unresolved target is not a node and therefore is not stored as an
edge at all ([§5.5](#55-unresolved-relationships)).

### 5.3 Edge identity and IDs

- **Relationship identity is the triple** `(subject.stable_key, predicate, object.stable_key)`.
  This triple is the canonical stable key of the edge and is stable across snapshots.
- **The edge row id is snapshot-scoped.** The stored `edge_id` is
  `edge:sha256(subject.stable_key || "\x1f" || predicate || "\x1f" || object.stable_key)`
  (`\x1f` = ASCII unit separator, which cannot occur in a stable key). The digest is deterministic,
  so the *same triple always yields the same `edge_id`*, but the stored edge is a row **within one
  snapshot** — edge identity does not span snapshots any more than node facts do.
- **Duplicate triples collapse to one edge.** Within a snapshot there is **at most one** edge per
  `(subject, predicate, object)` triple.

### 5.4 Multiple occurrences and multiple evidence

This is a decision, not an option:

- **Multiple source occurrences of the same relationship are one edge with multiple evidence
  records.** If `AuthService.login` calls `issueToken` on line 41 and again on line 90, that is
  **one** `calls` edge carrying **two** evidence records ([§6](#6-provenance-contract)). Occurrences
  are *not* modeled as distinct edges. This keeps the graph free of parallel edges, makes
  canonicalization ([§12](#12-canonical-graph-hash)) straightforward, and matches how consumers
  reason ("does A call B?" is a yes/no with citations).
- **Evidence records are ordered canonically** within the edge (by
  the total evidence ordering in [§12.3](#123-total-ordering-and-deduplication)).
- Truth class is a property of the **edge**, not of individual evidence records. All evidence on a
  single edge supports the same asserted relationship at the same truth class.

### 5.5 Unresolved relationships

An observed occurrence whose target the resolver cannot determine **does not become a guessed
edge**. It becomes a **diagnostic** (`RI-RES-UNRESOLVED` or `RI-RES-AMBIGUOUS`, [§8](#8-diagnostics-model))
that names the subject stable key and the unresolved reference text. This is the hard rule from #91:
*a guessed edge is never presented as observed* — and, in `ri.v1`, a guessed edge is never stored
at all.

### 5.6 Inferred property assertions

An inferred property is a separate graph-native **assertion**, never a replacement entity node.
This preserves the invariant that there is exactly one observed node per stable key while allowing
classifiers to make auditable claims about that entity.

`ri.v1` initially registers one assertion predicate:

| Predicate | Meaning | Subject | Value |
| --- | --- | --- | --- |
| `classified_as` | assigns an inferred architecture/layer classification | repository, module, file, or symbol node | canonical JSON object containing `classification` and optional deterministic qualifiers such as `confidence` |

The assertion record has this shape:

```json
{
  "kind": "assertion",
  "assertion_id": "assertion:sha256:c081743f9923c3f5036ebda30de9be443deb58002b6bfa1102f388e64a024d57",
  "subject": { "kind": "module", "stable_key": "mod:app/services" },
  "predicate": "classified_as",
  "value": { "classification": "business-logic-layer", "confidence": "heuristic" },
  "truth_class": "inferred",
  "producer": "architecture-classifier",
  "producer_version": "1.0.0",
  "derived_from": [
    { "kind": "node", "stable_key": "mod:app/services" },
    { "kind": "edge", "edge_id": "edge:sha256:e20b7e1135e0535ffb7c19cb2066a0645d9e980d2071816ddfc967431b774807" }
  ],
  "schema_version": "ri.v1"
}
```

Rules:

- `subject` MUST resolve to the one existing entity node in the same snapshot. An assertion MUST
  NOT create, overwrite, or change the truth class/properties of that node.
- `truth_class` MUST be `inferred`. The immediate classifier/inference producer and
  `producer_version` are REQUIRED, and `producer@producer_version` MUST appear in the snapshot's
  precomputed `producer_version_set` ([§3.3](#33-snapshot-identity)).
- `derived_from` MUST contain the assertion's immediate inputs using the tagged references in
  [§6.4](#64-observations-and-the-derived_from-reference-model). Recursive traversal exposes the
  exact source evidence supporting the classification; assertions do not copy or invent source
  spans.
- Build the assertion identity document from `schema_version`, `subject`, `predicate`, the complete
  canonical `value`, `truth_class`, `producer`, `producer_version`, and the sorted/deduplicated
  `derived_from` list. Normalize it under [§12.4](#124-normalization), serialize it with JCS
  ([§12.1](#121-serialization-format)), then compute
  `assertion_id = "assertion:sha256:" + lowercase_hex(sha256(canonical_identity_document))`.
- Persistence MUST enforce `UNIQUE(snapshot_id, assertion_id)`. Byte-identical duplicate assertions
  collapse; a change to value, immediate producer/version, or derivation produces a different
  assertion identity.
- Assertion predicates form their own registered namespace. Adding a predicate with new semantics
  is compatible within `ri.v1`; removing, renaming, or changing an existing predicate's meaning is
  breaking and requires `ri.v2` ([§9](#9-schema-versioning)).
- Query responses (#92) return assertions separately from nodes and edges, with their producer,
  truth class, value, immediate derivation references, and recursively resolvable evidence.

---

## 6. Provenance contract

### 6.1 The evidence record

The **minimum required** evidence record — the fields every stored piece of evidence MUST carry:

```json
{
  "path": "src/auth/service.ts",
  "start_line": 41,
  "end_line": 58,
  "extractor": "typescript-ast",
  "extractor_version": "1.0.0"
}
```

| Field | Type | Rule |
| --- | --- | --- |
| `path` | string | Repository-relative POSIX path, normalized per [§4.2](#42-path-normalization-applies-to-every-path-in-a-stable-key-or-evidence-record). REQUIRED. |
| `start_line` | integer | **One-based** line number of the first line of the span. REQUIRED. |
| `end_line` | integer | **One-based**, **inclusive** line number of the last line of the span. REQUIRED. |
| `extractor` | string | The extractor **or resolver** identifier that produced this evidence (`typescript-ast`, `python-ast`, `import-resolver`). REQUIRED. |
| `extractor_version` | string | Semantic version of that extractor/resolver. REQUIRED. |

### 6.2 Line and span rules (decided, not optional)

- **Lines are one-based.** The first line of a file is line 1.
- **`end_line` is inclusive.** A span covering only line 41 is `start_line: 41, end_line: 41`.
- **Text decoding and logical line count.** `ri.v1` line evidence is defined over a strict UTF-8
  decode of the stored file bytes. For decoded text, `logical_line_count = 1 + count(U+000A)`.
  Therefore an empty zero-byte text file has exactly one logical empty line, and text ending in `\n`
  has a final empty logical line. `\r\n` contributes one line because only its `\n` is counted; a
  lone `\r` does not increment the count. #89, #90, and #94 MUST use this exact convention.
- **Validation.** An evidence record is **valid** iff `1 ≤ start_line ≤ end_line ≤
  logical_line_count` for the file at the stored revision. A record that is reversed
  (`end_line < start_line`), zero or negative, or out of range is **invalid**.
- **An invalid span MUST NOT be stored as `observed` evidence.** The offending fact is dropped and
  an `RI-SPAN-INVALID` diagnostic is emitted naming the intended subject/object and the bad span. A
  fact without at least one valid evidence record MUST NOT be stored with truth class `observed`
  ([§7](#7-truth-classes)).
- **Whole-file facts.** A fact that is genuinely about the whole file (e.g. a `file` node, or a
  module-level property) is represented with `start_line: 1` and `end_line: logical_line_count`,
  plus `"granularity": "file"` on the evidence record. `granularity` defaults to `"span"` when
  omitted. This keeps every evidence record span-validatable while distinguishing "the whole file"
  from "lines 1–N happen to be the span."
- **Empty-file test vector.** A zero-byte `empty.txt` decodes to `""`, has
  `logical_line_count: 1`, and its whole-file evidence is exactly:

  ```json
  {
    "path": "empty.txt",
    "start_line": 1,
    "end_line": 1,
    "granularity": "file",
    "extractor": "repository-inventory",
    "extractor_version": "1.0.0"
  }
  ```

  `repository-inventory@1.0.0` must consequently be present in the planned
  `producer_version_set` for a pipeline that emits file nodes.
- **Binary and undecodable files.** A non-empty file containing a NUL byte is binary and emits
  an `info` `RI-SRC-BINARY`; a non-binary byte sequence that fails strict UTF-8 decoding emits an
  `error` `RI-SRC-MALFORMED`. In both cases no line-addressed node, assertion, observation, or
  relationship fact is emitted for that file. The diagnostic remains in the snapshot so absence is
  visible, and the snapshot may still complete. A zero-byte file is text, not binary.
- **Columns are deferred to v2.** `ri.v1` evidence is **line-granular only**. Optional
  `start_column`/`end_column` fields are **reserved** (a reader MUST ignore them if present) and
  are **not** produced by any `ri.v1` extractor. Adding column support is a compatible addition
  ([§9.1](#91-compatible-additions)) — it does not require `ri.v2` because it only adds optional
  fields — but the canonical hash treats their absence as canonical for `ri.v1` snapshots.

### 6.3 Multiple evidence, resolved/inferred evidence, and the revision tie

- **A fact MAY carry multiple evidence records** ([§5.4](#54-multiple-occurrences-and-multiple-evidence)).
  At least one is REQUIRED for an `observed` fact.
- **Resolved and inferred facts preserve their immediate derivation via `derived_from`.** A
  `resolved` edge normally references its source observations. An inferred assertion references the
  observations or canonical node/edge/assertion facts it consumed directly. Consumers recursively
  traverse these tagged references to the ultimate observations and evidence
  ([§6.4](#64-observations-and-the-derived_from-reference-model)); a producer MUST NOT flatten away
  an intermediate resolved fact or invent a span it did not read.
- **Evidence is tied to the exact stored revision.** Every `path`/span in an evidence record is
  resolved against the **snapshot's stored revision** ([§3](#3-revision-and-snapshot-identity)), not
  the current working tree. Because snapshots are immutable and revision-addressed, an evidence
  record remains valid for the life of the snapshot: line 41 of `service.ts` means line 41 of
  `service.ts` **at that commit/content hash**, forever. #94 validates that 100% of emitted evidence
  resolves to a real span in the stored revision.

### 6.4 Observations and the `derived_from` reference model

A `resolved` or `inferred` fact must be able to name the observed inputs it was computed from — but
an observed **occurrence** of an import, call, or route is not a node, and (before resolution) is
not an edge, because an unresolved occurrence never becomes an edge
([§5.5](#55-unresolved-relationships)). To reference such an input deterministically, `ri.v1`
defines the **observation**: the smallest stored, deterministic unit of observed syntax.

**What an observation is.** An extractor (#89/#90) emits, as part of its stored output, one
observation per observed syntactic occurrence it finds — each definition, import statement, call
site, and route declaration. An observation is an evidence-bearing provenance record, not a graph
node or edge; the corresponding node/edge fact carries its own truth class. A resolver (#91)
consumes observations, never the working tree. An observation that never resolves still exists (and
is what a `RI-RES-UNRESOLVED`/`RI-RES-AMBIGUOUS` diagnostic points at); it simply produces no edge.

**Exact JSON shape.**

```json
{
  "observation_id": "obs:sha256:d76b7bdbae85fc2016c49cf893a99ac8156cc98c3357582ab092836b94f0b424",
  "observed_kind": "import",
  "subject": { "kind": "file", "stable_key": "file:src/auth/service.ts" },
  "referent_text": "./tokens",
  "ordinal": 1,
  "evidence": {
    "path": "src/auth/service.ts", "start_line": 3, "end_line": 3,
    "extractor": "typescript-ast", "extractor_version": "1.0.0"
  }
}
```

| Field | Rule |
| --- | --- |
| `observation_id` | REQUIRED. Deterministic id (below). |
| `observed_kind` | REQUIRED. One of `definition`, `import`, `call`, `route`, `implements`, `contains`, `decorator`. Extensible as a compatible addition. |
| `subject` | REQUIRED. The stable key + kind of the node the occurrence is lexically inside (the enclosing file or symbol). This node MUST exist in the snapshot. |
| `referent_text` | OPTIONAL. The raw, unresolved reference as written in source (the import specifier `"./tokens"`, the callee text `issueToken`, the route path `"/login"`). Present for occurrences that a resolver will attempt to resolve; absent for pure `definition` observations. |
| `ordinal` | REQUIRED. One-based source order among observations whose other identity fields are identical. This disambiguates multiple identical occurrences on one line while columns are deferred. |
| `evidence` | REQUIRED. Exactly one evidence record ([§6.1](#61-the-evidence-record)) with a valid span ([§6.2](#62-line-and-span-rules-decided-not-optional)) against the stored revision. |

**Identity rule.** Build this observation identity document using the snapshot's immutable revision
and the observation fields:

```json
{
  "evidence": {
    "extractor": "typescript-ast",
    "extractor_version": "1.0.0",
    "path": "src/auth/service.ts",
    "start_line": 3,
    "end_line": 3
  },
  "observed_kind": "import",
  "ordinal": 1,
  "referent_text": "./tokens",
  "revision": { "kind": "git", "value": "0123456789abcdef0123456789abcdef01234567" },
  "schema_version": "ri.v1",
  "subject": { "kind": "file", "stable_key": "file:src/auth/service.ts" }
}
```

Normalize its strings and path under [§12.4](#124-normalization), serialize it with the JCS rules in
[§12.1](#121-serialization-format), and compute:

```text
observation_id = "obs:sha256:" + lowercase_hex(sha256(canonical_identity_document))
```

For an observation without `referent_text`, the identity document contains `"referent_text": null`;
omission is not an alternative encoding. `ordinal` handles the columns-deferred case
([§6.2](#62-line-and-span-rules-decided-not-optional)): two calls to `issueToken` on the same line
with otherwise identical identity fields get ordinals `1` and `2` in source order. Including the
immutable revision makes the ID revision-tied; including the extractor identifier and version avoids
collisions when different extractors report the same span. The subject stable key is safe here
because it is deterministic within the stored revision ([§4.1](#41-principle-and-cross-revision-guarantees)).

**The `derived_from` tagged reference.** A derived fact records its **immediate** inputs with one or
more of these exact shapes:

```json
[
  {
    "kind": "observation",
    "observation_id": "obs:sha256:d76b7bdbae85fc2016c49cf893a99ac8156cc98c3357582ab092836b94f0b424"
  },
  { "kind": "node", "stable_key": "mod:app/services" },
  { "kind": "edge", "edge_id": "edge:sha256:e20b7e1135e0535ffb7c19cb2066a0645d9e980d2071816ddfc967431b774807" },
  {
    "kind": "assertion",
    "assertion_id": "assertion:sha256:c081743f9923c3f5036ebda30de9be443deb58002b6bfa1102f388e64a024d57"
  }
]
```

Each reference MUST resolve in the same snapshot: observation refs by
`observation_id`, node refs by the snapshot-scoped stable key, edge refs by deterministic `edge_id`,
and assertion refs by deterministic `assertion_id`. Free text, placeholders, database row ids, and
cross-snapshot references are forbidden.

- A `resolved` edge MUST cite the source observation(s) it resolved. Its own required `producer` and
  `producer_version` identify the immediate resolver.
- An inferred assertion MUST cite the actual node, edge, assertion, or observation facts consumed
  directly by its classifier. If it consumes a resolved edge, it cites that edge rather than
  flattening the edge to the edge's observations. Recursive traversal then preserves the complete
  chain to the ultimate source evidence.
- `derived_from` is a set: pre-seal normalization removes byte-identical references and sorts the
  rest by the total ordering in [§12.3](#123-total-ordering-and-deduplication).
- Derivation references form a directed graph from each derived fact to its immediate inputs. The
  graph MUST be acyclic. Pre-seal validation resolves every reference and performs cycle detection;
  a missing target or cycle is a `fatal` internal-consistency error and the snapshot MUST NOT seal.

**How this behaves across resolution outcomes:**

- **Resolves.** The resolver emits a `resolved` edge whose `derived_from` names the import/call/route
  observation(s); the edge's own evidence points at the same occurrence span, and the edge records
  its resolver `producer` and `producer_version`. The observation remains stored.
- **Inference.** The classifier emits a separate inferred assertion ([§5.6](#56-inferred-property-assertions))
  whose immediate references may include resolved edges. It never creates a second entity node or
  erases the intermediate edge from the audit chain.
- **Unresolved / ambiguous.** No edge is produced. A `RI-RES-UNRESOLVED` / `RI-RES-AMBIGUOUS`
  diagnostic ([§8](#8-diagnostics-model)) carries the `observation_id` in its `details`
  (`{"observation_id": "obs:sha256:…"}`) and names the subject stable key. The observation remains
  stored so a consumer can still cite the unresolved occurrence — but it is never presented as an
  edge.
- **Hashing.** Observations participate in the canonical hash as their own ordered array
  ([§12.2](#122-what-is-hashed), [§12.3](#123-total-ordering-and-deduplication)); every tagged
  `derived_from` list is sorted, deduplicated, serialized, and hashed with its containing fact.
  Because all targets have deterministic identities, identical input and pipeline plans produce
  identical derivation bytes.

---

## 7. Truth classes

### 7.1 Definitions and emission rules

| Truth class | Definition | Emission rule |
| --- | --- | --- |
| **observed** | A direct syntax/entity-existence fact extracted from an **exact source span**. | MAY be emitted **only** by an **extractor** ([§2.2](#22-defined-terms)), and **only** with ≥1 valid evidence record whose span comes from that stored source. Entity nodes are observed and unique by stable key; no extractor may emit `observed` without valid evidence ([§6.2](#62-line-and-span-rules-decided-not-optional)). |
| **resolved** | A relationship produced by a **documented, deterministic resolution algorithm** over stored observed inputs. | MAY be emitted **only** as an **edge** by a resolver. The edge records `producer`, `producer_version`, and source-observation `derived_from` references. The algorithm MUST be documented (per #91) and deterministic: same inputs → same output. |
| **inferred** | A heuristic conclusion supported by evidence but **not guaranteed by syntax** (e.g. "this module is the authentication layer"). | MAY be emitted **only** as a separate **assertion** by a classifier/inference producer ([§5.6](#56-inferred-property-assertions)). It records its immediate producer/version and immediate tagged derivation references, and MUST be labeled inferred everywhere it surfaces. It MUST NOT duplicate or mutate an entity node. |
| **generated** | Human-facing **narrative** (prose explanation, AI answer, generated docs). | **Never stored as a fact in the snapshot graph** and never displayed as a deterministic repository fact ([§7.4](#74-generated-narrative)). |

### 7.2 Emission matrix (producer × truth class)

`✔` = permitted; blank = **forbidden**.

| Producer | observed | resolved | inferred | generated |
| --- | :---: | :---: | :---: | :---: |
| **Extractor** (`typescript-ast`, `python-ast`) | ✔ | | | |
| **Resolver** (`import-resolver`, `route-resolver`, `reference-resolver`) | | ✔ | | |
| **Classifier / inference** (architecture/layer classification) | | | ✔ (assertion only) | |
| **Narrative generator** (AI answer, doc prose) | | | | ✔ (never in graph) |
| **Legacy regex engine** (today's [`engine.py`](../../apps/backend/app/intelligence/engine.py)) | | | | see [§10.3](#103-legacy-regex-intelligence) — **not** `observed` |

The forbidden cells are load-bearing: an extractor MUST NOT emit `resolved` or `inferred`; a
resolver MUST NOT emit `observed` (it did not read a source span — it read stored facts); no
component may store `generated` narrative as a graph fact. A classifier MUST NOT emit an inferred
entity node; it emits a property assertion about the existing observed node.

Every `resolved` edge and `inferred` assertion MUST carry separate `producer` and
`producer_version` fields naming its immediate producer. The combined
`producer@producer_version` identifier MUST exist in the snapshot's precomputed
`producer_version_set`; otherwise pre-seal validation fails. This makes every derived fact
attributable without waiting until execution to discover which code participated.

### 7.3 Upgrades, retention, labeling

- **Truth class is fixed at emission and MUST NOT be upgraded.** A fact cannot be "promoted" from
  `resolved` to `observed`, or from `inferred` to `resolved`. A stronger claim requires a stronger
  *producer* re-deriving the fact from scratch in a **new snapshot**; it is never an in-place edit
  (snapshots are immutable — [§11](#11-snapshot-lifecycle-and-immutability)).
- **Supporting evidence and derivation are retained.** Downgrading is also not an in-place
  operation; every fact keeps its evidence and immediate `derived_from` references for the life of
  the snapshot, so consumers can recursively reconstruct the complete chain.
- **APIs and UIs MUST label `inferred` output.** The query API (#92) MUST expose `truth_class` on
  every fact, and any consumer (#95) MUST visibly distinguish `inferred` conclusions from
  `observed`/`resolved` ones. This is the machine-checkable successor to the
  [REPOSITORY_INTELLIGENCE.md](REPOSITORY_INTELLIGENCE.md) rule "never present a heuristic output as
  a deterministic fact."
- **An unresolved relationship produces a diagnostic, not a guessed edge** ([§5.5](#55-unresolved-relationships)).

### 7.4 Generated narrative

`generated` content — an AI answer, a prose architecture explanation — is **never stored in the
snapshot graph and never displayed as a deterministic repository fact.** It MAY be presented as
narrative *alongside* facts, but each concrete claim it makes MUST resolve to an underlying
`observed`/`resolved` fact with evidence (this is exactly the #95 proof workflow). This preserves
the existing invariant that the AI is a *consumer*, never a producer, of repository truth
([REPOSITORY_INTELLIGENCE.md](REPOSITORY_INTELLIGENCE.md), [CONTRIBUTING §11](../../CONTRIBUTING.md)).

---

## 8. Diagnostics model

### 8.1 The diagnostic record

Diagnostics are first-class, structured snapshot output. Every diagnostic record has:

| Field | Type | Rule |
| --- | --- | --- |
| `code` | string | Stable diagnostic code, e.g. `RI-EXT-UNSUPPORTED` ([§8.2](#82-diagnostic-codes-and-categories)). REQUIRED, stable across versions. |
| `category` | enum | One of [§8.2](#82-diagnostic-codes-and-categories). REQUIRED. |
| `severity` | enum | `fatal` \| `error` \| `warning` \| `info` ([§8.3](#83-severities)). REQUIRED. |
| `message` | string | Human-readable, deterministic (no timestamps, no absolute paths, no addresses). REQUIRED. |
| `path` | string \| null | Repository-relative POSIX path when applicable. |
| `span` | `{start_line,end_line}` \| null | One-based inclusive span when a location is known. |
| `producer` | string | Combined producer and version, e.g. `typescript-ast@1.0.0`. REQUIRED, and MUST occur in the snapshot's planned `producer_version_set`. |
| `subject` | stable key \| null | Related subject stable key when applicable. |
| `object` | stable key \| null | Related object stable key when applicable. |
| `details` | object | Deterministic structured details (e.g. `{ "candidates": ["a.ts::x","b.ts::x"] }`). Keys sorted; no volatile values. |

### 8.2 Diagnostic codes and categories

Codes are stable strings. The `ri.v1` baseline set (extensible as a compatible addition):

| Category | Code | Raised when |
| --- | --- | --- |
| unsupported construct | `RI-EXT-UNSUPPORTED` | A construct outside the extractor's published support matrix (#89/#90). |
| ambiguous resolution | `RI-RES-AMBIGUOUS` | A resolver finds more than one candidate target and cannot deterministically choose. |
| unresolved reference | `RI-RES-UNRESOLVED` | A resolver finds no target for an observed reference ([§5.5](#55-unresolved-relationships)). |
| extraction failure | `RI-EXT-FAILURE` | An extractor failed on an input it should have handled. |
| invalid span | `RI-SPAN-INVALID` | A produced span violates [§6.2](#62-line-and-span-rules-decided-not-optional). |
| stable-key collision | `RI-KEY-COLLISION` | Two distinct entities map to one stable key ([§4.3](#43-canonical-stable-key-formats)). |
| duplicate symbol | `RI-KEY-DUP-SYMBOL` | Overload/duplicate name resolved via `#<n>` discriminator (informational). |
| binary source | `RI-SRC-BINARY` | A non-empty file contains a NUL byte and is excluded from line-addressed extraction ([§6.2](#62-line-and-span-rules-decided-not-optional)). |
| malformed source | `RI-SRC-MALFORMED` | Source could not be parsed (syntax error, invalid encoding). |
| resource-limit skip | `RI-LIMIT-SKIP` | An input skipped by a resource budget (file too large, count cap — cf. today's 512 KB cap in [`engine.py`](../../apps/backend/app/intelligence/engine.py#L168) and #93 budgets). |
| path escape | `RI-SEC-PATH-ESCAPE` | A path escapes the repository root ([§4.2](#42-path-normalization-applies-to-every-path-in-a-stable-key-or-evidence-record)). |
| internal failure | `RI-INT-FAILURE` | An unexpected internal extractor/resolver failure. |

### 8.3 Severities

- **`fatal`** — the snapshot cannot be coherently built. Fails the snapshot ([§8.4](#84-which-diagnostics-fail-a-snapshot)).
- **`error`** — a specific fact could not be produced (a collision, an invalid span, an extraction
  failure on one file). The snapshot completes **with a visible gap**.
- **`warning`** — a fact was produced but with a caveat, or a relationship was left unresolved.
- **`info`** — informational (e.g. `RI-KEY-DUP-SYMBOL`, an unsupported construct that is expected).

### 8.4 Which diagnostics fail a snapshot

- A snapshot seals as **`completed`** iff it has **no `fatal` diagnostic**. `error`/`warning`/`info`
  diagnostics are recorded and the snapshot completes with the corresponding facts absent (visible
  gaps), because a partial-but-honest graph is more useful than no graph.
- A snapshot transitions to **`failed`** iff any `fatal` diagnostic is present — for example
  `RI-INT-FAILURE` at the pipeline level, or a condition that would make the stored graph
  internally inconsistent (a dangling edge that cannot be dropped safely).
- `RI-EXT-UNSUPPORTED`, `RI-RES-UNRESOLVED`, `RI-RES-AMBIGUOUS`, `RI-SRC-BINARY`, `RI-LIMIT-SKIP`,
  `RI-KEY-DUP-SYMBOL` are **never fatal** — they are the expected, honest output of a system that
  refuses to guess. `RI-SPAN-INVALID` and `RI-KEY-COLLISION` are `error` (drop the fact, complete
  the snapshot) unless they cascade into an incoherent graph, in which case they escalate to
  `fatal`.

---

## 9. Schema versioning

This RFC records the accepted `schema_version: "ri.v1"` as the value carried on every snapshot and
every fact-bearing API response. `ri.v1` is the value all conforming `ri.v1` artifacts carry.

### 9.1 Compatible additions

The following MAY be added within `ri.v1` without a version bump, because they cannot break a
conforming reader that ignores unknown optional fields:

- New **optional** fields on nodes, edges, assertions, evidence, or diagnostics.
- New **node kinds**, **predicates** (adding a predicate with new semantics — [§5.1](#51-canonical-predicates)),
  **assertion predicates**, **observation kinds**, or **diagnostic codes**.
- New producers (extractors, resolvers, classifiers, or inference producers) when they use existing
  fact semantics; they carry their own version and enter `producer_version_set`, not the schema
  version ([§9.4](#94-schema-version-vs-producer-version)).
- Populating a `reserved` field (e.g. columns — [§6.2](#62-line-and-span-rules-decided-not-optional)) with the documented semantics.

Readers MUST **ignore or safely preserve** unknown fields, unknown node kinds, **unknown
predicates**, unknown assertion predicates, unknown observation kinds, and unknown diagnostic codes
rather than failing.

### 9.2 Breaking changes (require `ri.v2`)

- Changing the **stable-key format** of any node kind ([§4](#4-node-identity-and-stable-keys)),
  including introducing a content-based symbol discriminator ([§15.1](#151-operational-costs-and-limitations-stated-honestly)).
- Changing the assertion identity document or tagged derivation-reference shapes
  ([§5.6](#56-inferred-property-assertions), [§6.4](#64-observations-and-the-derived_from-reference-model)).
- Changing **provenance semantics** (one-based → zero-based, inclusive → exclusive, path
  normalization rules).
- Changing **truth-class semantics** or the emission matrix in a way that reclassifies existing
  facts.
- **Removing, renaming, or changing the meaning of an existing relationship or assertion
  predicate** ([§5.1](#51-canonical-predicates), [§5.6](#56-inferred-property-assertions));
  removing or renaming a required field; changing a field's type or meaning.
- Changing **canonical-hash inputs or ordering** ([§12](#12-canonical-graph-hash)) such that an
  unchanged revision hashes differently.

A breaking change is introduced as a **new RFC** that proposes `ri.v2` for ratification; this
document is not edited to describe `ri.v2` behavior.

### 9.3 When `ri.v2` is required

Precisely when a change falls under [§9.2](#92-breaking-changes-require-riv2). If a proposed change
would make an existing sealed `ri.v1` snapshot mis-read or re-hash under the new rules, it is
breaking and requires `ri.v2`.

### 9.4 Schema version vs producer version

- **Schema version** (`ri.v1`) versions the *contract*.
- **Producer version** versions one implementation. Bumping `typescript-ast`, `import-resolver`, or
  `architecture-classifier` from `1.0.0` to `1.1.0` does **not** change the schema version; it
  changes the precomputed `producer_version_set` ([§3.3](#33-snapshot-identity)) and therefore
  produces a new snapshot for the same revision. The two axes are independent and both feed the
  canonical hash ([§12](#12-canonical-graph-hash)).

### 9.5 API response versioning (#92) and negotiation

- Every fact-bearing API response (#92) MUST include the `schema_version` it conforms to.
- Response **envelope** schemas are additionally versioned by the API (e.g. a `v1` route prefix or
  media-type parameter); a breaking envelope change is a new API version, decoupled from `ri.v*` so
  the wire shape can evolve independently of the fact schema.
- A reader that receives an **unsupported** `schema_version` MUST reject it explicitly (a clear
  error naming the versions it supports), MUST NOT silently coerce it, and MAY negotiate by
  requesting a supported version if the API offers one.

### 9.6 Historical snapshots retain their version

**Immutable historical snapshots retain their original `schema_version` forever.** A sealed `ri.v1`
snapshot is never rewritten to `ri.v2`; it remains a valid `ri.v1` artifact and is read under
`ri.v1` rules. New analysis after a schema bump produces `ri.v2` snapshots alongside the retained
`ri.v1` ones.

---

## 10. Migration policy

### 10.1 Database migrations, backfills, rollback

- Every schema change ships an **Alembic migration** that **downgrades cleanly**, per
  [CONTRIBUTING §10](../../CONTRIBUTING.md) (the migration test enforces up/down).
- **Backfills belong in the migration**, not in application startup ([CONTRIBUTING §10](../../CONTRIBUTING.md)).
  The #87 revision-column backfill and any snapshot-table introduction (#88) follow this rule.
- Migrations are **transactional** with uniqueness constraints and foreign keys on snapshot/node/
  edge/provenance tables (#88).
- **Rollback/downgrade** must leave the database in the pre-migration shape without data loss for
  columns that existed before. Introducing immutable snapshot tables is additive; downgrade drops
  the new tables (accepting that snapshots created under the new schema are lost on downgrade — an
  explicitly documented cost, not a silent one).

### 10.2 Migration between schema versions: re-extraction, not transformation

- The revision-identity migration (#87) is a **transformation**: it moves an existing typed value
  (`commitSha`) from a JSON blob into an indexed column. Transformation is allowed **only** for
  values that are already exact and typed.
- **Graph facts are never transformed across schema versions.** Moving from `ri.v1` to a future
  `ri.v2` graph MUST be done by **re-extraction** (re-running extractors/resolvers against the
  stored revision to produce a fresh `ri.v2` snapshot), never by mechanically rewriting `ri.v1` rows
  into `ri.v2` shape. Old `ri.v1` snapshots are retained under their original version
  ([§9.6](#96-historical-snapshots-retain-their-version)).

### 10.3 Legacy regex intelligence

The current `repo_metadata["intelligence"]` blob (produced by today's regex
[`engine.py`](../../apps/backend/app/intelligence/engine.py), carrying **no line spans**) is handled
as follows — this is a decision the RFC must not leave open:

- **Legacy regex facts are NOT promoted to `observed`.** They have no valid spans and no
  extractor/version provenance; per [§6.2](#62-line-and-span-rules-decided-not-optional) and
  [§7.1](#71-definitions-and-emission-rules) they cannot be `observed`.
- **They are retained as explicitly legacy/unverified data, and superseded by reanalysis.** The
  legacy blob MAY remain readable, clearly labeled `legacy_unverified` (never `observed`,
  `resolved`, or `inferred`), until a fresh `ri.v1` snapshot exists for the repository. A `ri.v1`
  snapshot, once sealed, is the authoritative source for that repository/revision and the consumer
  migration (#95) reads only snapshots.
- The legacy blob is **not migrated into the snapshot graph**. Its facts are not copied into node/
  edge tables. The path to a real graph is reanalysis (#88 + #89/#90/#91), not transformation of
  regex output.

### 10.4 Failure and recovery

- A migration that fails MUST roll back within its transaction, leaving the prior schema intact.
- A partially built snapshot that fails ([§11](#11-snapshot-lifecycle-and-immutability)) never
  becomes visible as `completed`; recovery is a fresh analysis run (#93 job lifecycle), not repair
  of a half-sealed snapshot.

---

## 11. Snapshot lifecycle and immutability

### 11.1 States

`ri.v1` defines exactly these snapshot states:

- **`building`** — the snapshot is being populated. Its complete semantic identity, including the
  planned `producer_version_set`, was fixed before the job was enqueued. Facts and diagnostics are
  being written. Not visible to consumers as an authoritative result.
- **`completed`** (a.k.a. **sealed**) — validation passed, the canonical hash is computed and
  stored, and the snapshot is **immutable**.
- **`failed`** — a `fatal` diagnostic ([§8.4](#84-which-diagnostics-fail-a-snapshot)) or an
  unrecoverable error occurred. The snapshot did not seal; it is retained for diagnosis but is never
  served as an authoritative graph.

### 11.2 Sealing transaction and pre-seal validation

- **The seal is a single database transaction** that: (a) validates the snapshot, (b) computes and
  stores the canonical graph hash ([§12](#12-canonical-graph-hash)), and (c) flips the status from
  `building` to `completed`. Either all three commit or none do. There is no observable
  intermediate "sealed but unvalidated" state.
- **Required validation before sealing:**
  1. Every `observed` fact has ≥1 valid evidence record ([§6.2](#62-line-and-span-rules-decided-not-optional)).
  2. Every edge's subject and object reference nodes that exist in the snapshot (or a permitted
     external `dependency` node) ([§5.2](#52-subject-and-object-identity)).
  3. No `fatal` diagnostic is present ([§8.4](#84-which-diagnostics-fail-a-snapshot)).
  4. Every stable key is well-formed ([§4](#4-node-identity-and-stable-keys)); collisions are
     resolved or recorded.
  5. Exactly one `repo:root` node exists; every other node stable key is unique under
     `(snapshot_id, stable_key)`; no inferred assertion duplicates or mutates an entity node.
  6. Every output producer is declared in the precomputed `producer_version_set`. Every resolved
     edge and inferred assertion has an immediate `producer`/`producer_version` pair matching that
     set, and every diagnostic's combined `producer@version` identifier matches it.
  7. Every `derived_from` reference resolves to an observation or canonical fact in the same
     snapshot, and the derivation graph is acyclic ([§6.4](#64-observations-and-the-derived_from-reference-model)).
  8. Assertion subjects and all edge endpoints resolve; assertion identities recompute from their
     canonical identity documents; duplicate semantic edge records have been consolidated.
  9. Every set-semantic array is normalized, sorted, and deduplicated under the total rules in
     [§12.3](#123-total-ordering-and-deduplication).
  10. The canonical hash is reproducible (computing it twice yields the same value).

### 11.3 Immutability

- **A completed snapshot is immutable.** Its planned producer set, optional `actual_producers`,
  nodes, edges, assertions, observations, evidence, derivation references, diagnostics, and hash
  MUST NOT change.
- **Mutation attempts are rejected, not ignored.** A write against a `completed` snapshot MUST raise
  an error (#88 tests this). This is the successor to today's silent-overwrite behavior, where
  re-analysis rewrites `repo_metadata["intelligence"]` in place.
- **Corrections and reanalysis come from a NEW snapshot produced by changed inputs**
  ([§3.4](#34-reanalysis-reuse-and-idempotency)). There is no edit-in-place path, and an analysis
  request whose composite identity matches a sealed snapshot reuses it rather than producing a
  correction.
- **Diagnostics become immutable at seal**, together with the facts — they are part of the sealed,
  hashed artifact.

### 11.4 Failed extraction, cancellation, retry (#93 interaction)

- A `building` snapshot that hits a `fatal` condition transitions to `failed` and is never served.
- **The job's completion is the thing that seals the snapshot** (#93): a durable job's successful
  terminal step is the sealing transaction. #93 and #88 MUST agree that "job completed" ⇔ "snapshot
  sealed."
- **Cancellation** (#93) aborts a `building` snapshot; the aborted snapshot is discarded or marked
  `failed`, never `completed`.
- **Retry** (#93) starts a **new** `building` attempt. Retries and failed attempts MAY accumulate
  multiple `building`/`failed` rows for one composite identity, but **only one snapshot may ever
  become `sealed`/`completed`** for that identity ([§3.4](#34-reanalysis-reuse-and-idempotency)); a
  retry never resumes and seals a previously abandoned attempt.

### 11.5 Concurrency and idempotency

- **Idempotent submission** (#93): a request for a composite identity
  ([§3.3](#33-snapshot-identity)) that already has a sealed snapshot **MUST reuse** it and **MUST
  NOT** produce a second sealed snapshot ([§3.4](#34-reanalysis-reuse-and-idempotency)).
- **Concurrent builds** for the same composite identity **MUST coordinate so at most one attempt
  seals**; after one seals, the others reuse the sealed result. The uniqueness constraint permitting
  at most one sealed snapshot per composite identity ([§3.3](#33-snapshot-identity)) is the backstop.

---

## 12. Canonical graph hash

The canonical graph hash makes snapshot output **deterministic and comparable** and is the basis
for #88's stored hash and #94's determinism check. **Identical input revision, schema version,
planned producer versions, and configuration MUST produce the same canonical hash, independent of
record insertion order.**

### 12.1 Serialization format

- Canonical serialization is **UTF-8 JSON with lexicographically sorted object keys, no
  insignificant whitespace, and no trailing newline** (RFC 8785 JSON Canonicalization Scheme
  semantics). Numbers are integers (line numbers); no floats appear in hashed content.
- The hash is `sha256` of the canonical serialization, stored as `sha256:<hex>`.

### 12.2 What is hashed

A single canonical document with five ordered arrays plus scalar inputs:

```jsonc
{
  "schema_version": "ri.v1",
  "revision": { "kind": "...", "value": "..." },
  "producer_version_set": [
    "architecture-classifier@1.0.0",
    "import-resolver@1.0.0",
    "python-ast@1.0.0",
    "reference-resolver@1.0.0",
    "repository-inventory@1.0.0",
    "route-resolver@1.0.0",
    "typescript-ast@1.0.0"
  ],
  "config_hash": "sha256:...",
  "nodes":        ["<normalized, deduplicated, totally ordered node records>"],
  "edges":        ["<normalized, consolidated, totally ordered edge records>"],
  "assertions":   ["<normalized, deduplicated, totally ordered assertion records>"],
  "observations": ["<normalized, deduplicated, totally ordered observation records>"],
  "diagnostics":  ["<normalized, deduplicated, totally ordered diagnostic records>"]
}
```

### 12.3 Total ordering and deduplication

Every hashed array uses the same final procedure:

1. Normalize the complete record under [§12.4](#124-normalization), including its nested arrays.
2. Serialize that complete normalized record to JCS bytes ([§12.1](#121-serialization-format)).
3. Remove byte-identical duplicate records.
4. Sort by the semantic tuple documented below, then by the **complete JCS record bytes as the final
   tie-breaker**. Therefore two unequal records can never compare equal, even when all earlier tuple
   fields match.

The semantic tuples are:

- **Nodes:** `(stable_key, complete_record_jcs)`. Two unequal node records with the same stable key
  are not alternative orderings; they violate the one-entity invariant and pre-seal validation MUST
  reject them ([§4.1](#41-principle-and-cross-revision-guarantees)).
- **Edges:** first consolidate every `(subject.stable_key, predicate, object.stable_key)` group into
  one edge by set-unioning and normalizing `evidence` and `derived_from`. All other fields, including
  truth class and immediate producer/version, MUST agree or the snapshot fails. Sort consolidated
  edges by `(subject.stable_key, predicate, object.stable_key, complete_record_jcs)`.
- **Assertions:** `(subject.stable_key, predicate, assertion_id, complete_record_jcs)`.
- **Observations:** `(observation_id, complete_record_jcs)`.
- **Evidence within a fact:** `(path, start_line, end_line, granularity, extractor,
  extractor_version, complete_record_jcs)`. Canonicalization materializes the default
  `granularity: "span"`; all other present optional evidence fields participate through the final
  JCS bytes.
- **Tagged `derived_from` references:** `(kind_rank, referenced_identity, complete_record_jcs)`,
  where the fixed rank is `observation=0`, `node=1`, `edge=2`, `assertion=3`, and the referenced
  identity is respectively `observation_id`, `stable_key`, `edge_id`, or `assertion_id`. References
  are set-semantic and therefore sorted and deduplicated.
- **Diagnostics:** `(code, category, severity, path_or_empty, span.start_line_or_0,
  span.end_line_or_0, producer, subject_or_empty, object_or_empty, message,
  canonical_details_jcs, complete_record_jcs)`. This includes the complete span, immediate producer,
  and every deterministic `details` field; diagnostics that differ only in optional/details content
  consequently still have a deterministic order.
- **`producer_version_set`:** lexicographically sort identifiers by normalized UTF-8 byte order and
  remove duplicates before both identity lookup and hashing.

For any property/configuration array whose documented semantics are a **set**, normalize each
element, sort by its complete JCS bytes, and remove byte-identical duplicates. Arrays whose order
changes meaning (for example an ordered resolver pipeline) preserve their declared order. Every
producer MUST declare each array field as set-semantic or order-significant; an undeclared array is
invalid and prevents sealing. Thus the same logical output generated in different insertion orders
always hashes identically.

### 12.4 Normalization

- All paths are repository-relative POSIX, normalized per [§4.2](#42-path-normalization-applies-to-every-path-in-a-stable-key-or-evidence-record).
- All strings are **Unicode NFC**.
- Evidence with omitted `granularity` is materialized as `"granularity": "span"` before sorting and
  hashing, so omitted-default and explicit-default encodings cannot diverge.
- Reserved-but-absent optional fields (e.g. columns in `ri.v1`) are **omitted**, and their omission
  is canonical for `ri.v1`. A producer that emits a reserved column field is non-conforming and the
  snapshot MUST NOT seal.

### 12.5 Excluded volatile fields

The following MUST be **excluded** from the hash, because they vary between otherwise-identical
runs: `snapshot_id`, `repository_id`, any `created_at`/`sealed_at`/wall-clock timestamp, any
autoincrement/database row id, host/environment identifiers, and optional execution-audit metadata
such as `actual_producers`. `revision.ref` (a moving branch name) is **excluded**; `revision.value`
(the immutable SHA/content hash) is **included**. Canonical `edge_id`, `assertion_id`, and
`observation_id` values are deterministic content identities and are included where present.

`repository_id` remains part of snapshot ownership and semantic identity ([§3.3](#33-snapshot-identity))
but is deliberately excluded from graph-content hashing. The repository entity key is `repo:root`,
so an opaque database UUID cannot leak into the node array; equivalent stored source and pipeline
inputs can produce the same graph hash across separate repository records.

### 12.6 Diagnostics in the hash

Diagnostics **are included** in the canonical document ([§12.2](#122-what-is-hashed)) because a
change in what the pipeline *could not* handle is a real change in the snapshot's meaning. Their
`message` field MUST be deterministic (no timestamps, no absolute paths) so it does not destabilize
the hash. If an implementation needs to compare graphs while ignoring diagnostics, it MAY compute a
secondary `graph_only_hash`, but the **primary** `canonical_graph_hash`
covers all five arrays (`nodes`, `edges`, `assertions`, `observations`, `diagnostics`) and is the one
stored and compared for determinism. A secondary graph-only hash, if exposed, covers
`nodes`+`edges`+`assertions` and follows the same total-order rules.

### 12.7 `config_hash`

`config_hash` is the deterministic fingerprint of the **output-affecting analysis configuration**. It
is a component of snapshot identity ([§3.3](#33-snapshot-identity)) and an input to the canonical
graph hash ([§12.2](#122-what-is-hashed)), so it MUST be computed by exactly this procedure:

1. **Included (output-affecting) configuration only.** `config_hash` covers configuration that can
   change graph output, for example: enabled-producer selection and pipeline order; extractor,
   resolver, and classifier support-matrix options; resource limits that change *what is extracted*
   (max file size, file-count caps, per-file node caps — cf. the current 512 KB cap in
   [`engine.py`](../../apps/backend/app/intelligence/engine.py#L168)); and any language/parse options
   that alter emitted facts.
2. **Excluded operational settings.** Configuration that cannot change graph output MUST be excluded:
   database URL, storage path, worker/queue concurrency, timeouts and retry counts (#93), log level,
   rate-limit budgets, and credentials. (Note: producer **versions** are identity inputs but are
   carried separately in `producer_version_set` ([§3.3](#33-snapshot-identity)); they
   are not part of `config_hash`.)
3. **Canonical serialization.** Serialize the included configuration as a canonical JSON document
   using the **same JCS rules** as [§12.1](#121-serialization-format): UTF-8, lexicographically
   **sorted object keys**, no insignificant whitespace, no trailing newline.
4. **String normalization.** Normalize all string keys and values to **Unicode NFC**; normalize any
   path-valued setting per [§4.2](#42-path-normalization-applies-to-every-path-in-a-stable-key-or-evidence-record).
5. **Array ordering.** **Sort arrays whose semantics are sets** (e.g. enabled extractors or
   classifiers) ascending; **preserve declared order for arrays whose order affects output** (e.g.
   an ordered resolver pipeline). Each array's setting documents which rule applies; when in doubt a
   setting is treated as order-significant.
6. **Hash.** Compute `sha256` over the canonical UTF-8 bytes and store as `sha256:<lowercase-hex>`.
7. **Empty/default configuration.** The hash input represents the **effective** output-affecting
   configuration after defaults are applied, not only user-supplied overrides. Every output-affecting
   default MUST therefore appear explicitly. The empty configuration is used only when no such
   setting exists; it is the canonical JSON object `{}`, whose
   `config_hash` is therefore the SHA-256 of the two bytes `{}` —
   `sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`.
   An implementation MUST NOT use this empty hash merely because the caller supplied no overrides.

**Normative example.** Configuration enabling three extractors, three resolvers, one classifier, and a
512 KB file cap:

```jsonc
// input (pre-canonicalization)
{ "max_file_bytes": 524288,
  "extractors": ["typescript-ast", "python-ast", "repository-inventory"],
  "resolvers":  ["route-resolver", "import-resolver", "reference-resolver"],
  "classifiers": ["architecture-classifier"] }
```

```text
canonical bytes:
{"classifiers":["architecture-classifier"],"extractors":["python-ast","repository-inventory","typescript-ast"],"max_file_bytes":524288,"resolvers":["import-resolver","reference-resolver","route-resolver"]}
config_hash = "sha256:" + hex(sha256(canonical bytes))
            = "sha256:48e96ba328a03db38556f22d2831d171b82e1ce9287c575328de4bc249da1abe"
```

`config_hash` MUST be referenced by both snapshot identity ([§3.3](#33-snapshot-identity)) and the
canonical graph hash ([§12.2](#122-what-is-hashed)); the same configuration therefore always yields
the same identity and hash inputs.

---

## 13. Security and ownership

These are requirements on every downstream issue, restating and extending the existing invariants in
[CONTRIBUTING §11](../../CONTRIBUTING.md), [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md), and the #63/#65
owner-scoping work:

- **Repository and snapshot queries MUST be owner-scoped at the service layer** (#92), consistent
  with #63. Every snapshot lookup goes through owner-scoped accessors (like
  [`RepositoryRepository.get_for_owner`](../../apps/backend/app/repositories/repository_repository.py#L25)); a cross-owner
  request receives the same `404` as a missing one and never learns the resource exists. A query API
  that bypasses owner scoping reopens exactly the gap #63 closed.
- **Evidence MUST NOT permit filesystem traversal.** Every path is repository-relative and
  normalized per [§4.2](#42-path-normalization-applies-to-every-path-in-a-stable-key-or-evidence-record);
  a path escaping the repository root is rejected with `RI-SEC-PATH-ESCAPE` and never stored.
- **Paths remain repository-relative** everywhere — in stable keys, evidence, and diagnostics.
  Absolute paths and host paths MUST NOT appear in any stored fact, diagnostic, or API response.
- **Secrets and repository contents MUST NOT be logged**, per [CONTRIBUTING §11.8](../../CONTRIBUTING.md)
  and the existing log redaction ([SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)). Diagnostic `message`
  and `details` MUST NOT embed source content or secrets.
- **Query APIs MUST NOT read the working tree** (#92). The query path reads the snapshot store only;
  no filesystem read anywhere in it. #95 asserts this with a test that the migrated consumer performs
  zero filesystem reads.
- **Consumers cannot create independent parsers** ([CONTRIBUTING §11.1–11.3](../../CONTRIBUTING.md),
  [REPOSITORY_INTELLIGENCE.md](REPOSITORY_INTELLIGENCE.md)). A consumer that can only query cannot
  invent its own parser; this contract makes the architectural invariant enforceable rather than
  aspirational.

---

## 14. Normative examples

Each example is illustrative of the `ri.v1` shape; field names are normative, surrounding envelope
is not.

### 14.1 Observed TypeScript symbol

```json
{
  "kind": "node",
  "node_kind": "symbol",
  "stable_key": "src/auth/service.ts::AuthService.login",
  "name": "login",
  "language": "typescript",
  "truth_class": "observed",
  "evidence": [
    { "path": "src/auth/service.ts", "start_line": 41, "end_line": 58,
      "extractor": "typescript-ast", "extractor_version": "1.0.0" }
  ],
  "schema_version": "ri.v1"
}
```

### 14.2 Observed Python function with a decorator

```json
{
  "kind": "node",
  "node_kind": "symbol",
  "stable_key": "app/api/routes/auth.py::login",
  "name": "login",
  "language": "python",
  "truth_class": "observed",
  "properties": { "decorators": ["router.post"] },
  "evidence": [
    { "path": "app/api/routes/auth.py", "start_line": 22, "end_line": 35,
      "extractor": "python-ast", "extractor_version": "1.0.0" }
  ],
  "schema_version": "ri.v1"
}
```

### 14.3 Resolved import / route relationship

```json
{
  "kind": "edge",
  "edge_id": "edge:sha256:e20b7e1135e0535ffb7c19cb2066a0645d9e980d2071816ddfc967431b774807",
  "subject":  { "kind": "symbol", "stable_key": "app/api/routes/auth.py::login" },
  "predicate": "routes_to",
  "object":   { "kind": "symbol", "stable_key": "app/services/auth_service.py::AuthService.authenticate" },
  "truth_class": "resolved",
  "producer": "route-resolver",
  "producer_version": "1.0.0",
  "evidence": [
    { "path": "app/api/routes/auth.py", "start_line": 21, "end_line": 21,
      "extractor": "route-resolver", "extractor_version": "1.0.0" }
  ],
  "derived_from": [
    {
      "kind": "observation",
      "observation_id": "obs:sha256:86730689178079a960cf3019128882be518e92e7cdedb67d3dd4351f0201fc7e"
    }
  ],
  "schema_version": "ri.v1"
}
```

The referenced observation is the observed route declaration, e.g.:

```json
{
  "observation_id": "obs:sha256:86730689178079a960cf3019128882be518e92e7cdedb67d3dd4351f0201fc7e",
  "observed_kind": "route",
  "subject": { "kind": "symbol", "stable_key": "app/api/routes/auth.py::login" },
  "referent_text": "/login",
  "ordinal": 1,
  "evidence": { "path": "app/api/routes/auth.py", "start_line": 21, "end_line": 21,
                "extractor": "python-ast", "extractor_version": "1.0.0" }
}
```

The observation ID above is computed under [§6.4](#64-observations-and-the-derived_from-reference-model)
against the immutable Git revision in [§14.8](#148-git-revision-identity). The edge ID is the
SHA-256 of its canonical relationship triple under [§5.3](#53-edge-identity-and-ids).

### 14.4 Inferred architecture classification (must be labeled inferred)

The entity exists exactly once as an observed node:

```json
{
  "kind": "node",
  "node_kind": "module",
  "stable_key": "mod:app/services",
  "name": "services",
  "truth_class": "observed",
  "evidence": [
    {
      "path": "app/services/__init__.py",
      "start_line": 1,
      "end_line": 1,
      "granularity": "file",
      "extractor": "repository-inventory",
      "extractor_version": "1.0.0"
    }
  ],
  "schema_version": "ri.v1"
}
```

The classification is a separate inferred assertion:

```json
{
  "kind": "assertion",
  "assertion_id": "assertion:sha256:c081743f9923c3f5036ebda30de9be443deb58002b6bfa1102f388e64a024d57",
  "subject": { "kind": "module", "stable_key": "mod:app/services" },
  "predicate": "classified_as",
  "value": { "classification": "business-logic-layer", "confidence": "heuristic" },
  "truth_class": "inferred",
  "producer": "architecture-classifier",
  "producer_version": "1.0.0",
  "derived_from": [
    { "kind": "node", "stable_key": "mod:app/services" },
    {
      "kind": "edge",
      "edge_id": "edge:sha256:e20b7e1135e0535ffb7c19cb2066a0645d9e980d2071816ddfc967431b774807"
    }
  ],
  "schema_version": "ri.v1"
}
```

The classifier consumes the observed module node and resolved route edge directly, so those are its
immediate references. Following the edge reaches its route observation and exact line evidence. The
assertion never overwrites the observed node. Its ID is the verified hash of the identity document
defined in [§5.6](#56-inferred-property-assertions).

### 14.5 Unresolved / ambiguous diagnostic (not a guessed edge)

```json
{
  "code": "RI-RES-AMBIGUOUS",
  "category": "ambiguous resolution",
  "severity": "warning",
  "message": "import 'utils' resolves to more than one candidate module",
  "path": "src/app/index.ts",
  "span": { "start_line": 3, "end_line": 3 },
  "producer": "import-resolver@1.0.0",
  "subject": "file:src/app/index.ts",
  "object": null,
  "details": {
    "observation_id": "obs:sha256:d8544c0e7ec142ab6d1cf98919657cf0d289d7f9490d9d03b55d8aab4fafe98c",
    "candidates": ["src/app/utils.ts", "src/shared/utils/index.ts"]
  }
}
```

The `observation_id` names the stored observed import occurrence that could not be resolved. No
edge is created ([§5.5](#55-unresolved-relationships)); the observation remains stored so a consumer
can still cite the unresolved import.

The referenced observation is:

```json
{
  "observation_id": "obs:sha256:d8544c0e7ec142ab6d1cf98919657cf0d289d7f9490d9d03b55d8aab4fafe98c",
  "observed_kind": "import",
  "subject": { "kind": "file", "stable_key": "file:src/app/index.ts" },
  "referent_text": "utils",
  "ordinal": 1,
  "evidence": { "path": "src/app/index.ts", "start_line": 3, "end_line": 3,
                "extractor": "typescript-ast", "extractor_version": "1.0.0" }
}
```

Its ID is computed against the immutable Git revision in [§14.8](#148-git-revision-identity).

### 14.6 Unsupported construct

```json
{
  "code": "RI-EXT-UNSUPPORTED",
  "category": "unsupported construct",
  "severity": "info",
  "message": "dynamic import() is outside the TypeScript support matrix",
  "path": "src/plugins/loader.ts",
  "span": { "start_line": 12, "end_line": 12 },
  "producer": "typescript-ast@1.0.0",
  "subject": "file:src/plugins/loader.ts",
  "object": null,
  "details": { "construct": "dynamic-import" }
}
```

### 14.7 Upload revision identity

```json
{
  "snapshot_id": "snap_9c2…",
  "repository_id": "repo_7f3…",
  "revision": { "kind": "upload", "value": "sha256:f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d", "ref": null },
  "schema_version": "ri.v1",
  "producer_version_set": [
    "architecture-classifier@1.0.0",
    "import-resolver@1.0.0",
    "python-ast@1.0.0",
    "reference-resolver@1.0.0",
    "repository-inventory@1.0.0",
    "route-resolver@1.0.0",
    "typescript-ast@1.0.0"
  ],
  "config_hash": "sha256:48e96ba328a03db38556f22d2831d171b82e1ce9287c575328de4bc249da1abe"
}
```

The upload hash above is the SHA-256 of the illustrative UTF-8 fixture bytes `fixture`.

### 14.8 Git revision identity

```json
{
  "snapshot_id": "snap_1a4…",
  "repository_id": "repo_7f3…",
  "revision": { "kind": "git", "value": "9f1d0c7a2b6e4c5d8f3a1b0c7d9e2f4a6b8c0d1e", "ref": "refs/heads/main" },
  "schema_version": "ri.v1",
  "producer_version_set": [
    "architecture-classifier@1.0.0",
    "import-resolver@1.0.0",
    "python-ast@1.0.0",
    "reference-resolver@1.0.0",
    "repository-inventory@1.0.0",
    "route-resolver@1.0.0",
    "typescript-ast@1.0.0"
  ],
  "config_hash": "sha256:48e96ba328a03db38556f22d2831d171b82e1ce9287c575328de4bc249da1abe"
}
```

### 14.9 Multiple evidence occurrences on one edge

```json
{
  "kind": "edge",
  "edge_id": "edge:sha256:90594a4734e993838e2db11f9d3bb5ede0cab2f1c70730ca8c4ab407c93bd69e",
  "subject":  { "kind": "symbol", "stable_key": "src/auth/service.ts::AuthService.login" },
  "predicate": "calls",
  "object":   { "kind": "symbol", "stable_key": "src/auth/tokens.ts::issueToken" },
  "truth_class": "resolved",
  "producer": "reference-resolver",
  "producer_version": "1.0.0",
  "evidence": [
    { "path": "src/auth/service.ts", "start_line": 41, "end_line": 41,
      "extractor": "reference-resolver", "extractor_version": "1.0.0" },
    { "path": "src/auth/service.ts", "start_line": 90, "end_line": 90,
      "extractor": "reference-resolver", "extractor_version": "1.0.0" }
  ],
  "derived_from": [
    {
      "kind": "observation",
      "observation_id": "obs:sha256:ad475fae87c8121b76673172a560885335661f68ea90e4b5fa661be9b884f24a"
    },
    {
      "kind": "observation",
      "observation_id": "obs:sha256:082048c4fd048043fbc22da52166e7fab6f37fa0f8803a1b3444b412b6ba1dd4"
    }
  ],
  "schema_version": "ri.v1"
}
```

> The two call-site occurrences are two `observed_kind: "call"` observations (lines 41 and 90) that
> both resolve to the same callee, so they collapse to **one** `calls` edge with two evidence records
> and two `derived_from` observation references ([§5.4](#54-multiple-occurrences-and-multiple-evidence)).

The referenced observations are:

```json
[
  {
    "observation_id": "obs:sha256:ad475fae87c8121b76673172a560885335661f68ea90e4b5fa661be9b884f24a",
    "observed_kind": "call",
    "subject": { "kind": "symbol", "stable_key": "src/auth/service.ts::AuthService.login" },
    "referent_text": "issueToken",
    "ordinal": 1,
    "evidence": { "path": "src/auth/service.ts", "start_line": 41, "end_line": 41,
                  "extractor": "typescript-ast", "extractor_version": "1.0.0" }
  },
  {
    "observation_id": "obs:sha256:082048c4fd048043fbc22da52166e7fab6f37fa0f8803a1b3444b412b6ba1dd4",
    "observed_kind": "call",
    "subject": { "kind": "symbol", "stable_key": "src/auth/service.ts::AuthService.login" },
    "referent_text": "issueToken",
    "ordinal": 1,
    "evidence": { "path": "src/auth/service.ts", "start_line": 90, "end_line": 90,
                  "extractor": "typescript-ast", "extractor_version": "1.0.0" }
  }
]
```

Both IDs are computed against the immutable Git revision in [§14.8](#148-git-revision-identity).

### 14.10 Generated narrative — explicitly excluded from deterministic facts

```json
{
  "kind": "generated",
  "truth_class": "generated",
  "stored_in_graph": false,
  "text": "Authentication is handled by AuthService.login, which issues a token via issueToken.",
  "claims": [
    { "kind": "node", "stable_key": "src/auth/service.ts::AuthService.login" },
    {
      "kind": "edge",
      "edge_id": "edge:sha256:90594a4734e993838e2db11f9d3bb5ede0cab2f1c70730ca8c4ab407c93bd69e"
    }
  ]
}
```

> The narrative object above is **never written to the snapshot graph** (`stored_in_graph: false`)
> and is never a node or edge. Each `claim` MUST point at an `observed`/`resolved` fact with
> evidence; a claim with no resolvable span is not displayed as a fact ([§7.4](#74-generated-narrative), #95).

---

## 15. Alternatives and consequences

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| **Storage model** | Immutable, sealed, revision-addressed snapshots ([§11](#11-snapshot-lifecycle-and-immutability)) | The current mutable JSON blob on `repo_metadata` | The blob is not queryable, not indexable, not versioned, and silently rewrites history on every re-analysis ([REPOSITORY_INTELLIGENCE.md](REPOSITORY_INTELLIGENCE.md)). Immutability is what makes any claim about provenance or diffs defensible. |
| **Node identity** | Deterministic stable keys ([§4](#4-node-identity-and-stable-keys)) | Random/autoincrement ids | Random ids are not comparable across snapshots or revisions; every downstream item (#88–#94) needs identity that is a pure function of the source. |
| **Repository node identity** | Snapshot-scoped constant `repo:root` ([§4.3](#43-canonical-stable-key-formats)) | Embed opaque `repository_id` as `repo:<repository_id>` | Repository IDs are generated database ownership keys. Embedding one would violate stable-key rules and make equivalent graph content hash differently after re-import. |
| **Inferred entity properties** | Separate deterministic property assertions ([§5.6](#56-inferred-property-assertions)) | Emit a second inferred node or mutate the observed node | One entity cannot have two existence records/truth classes. Assertions preserve one observed node and keep classifier output independently attributable and queryable. |
| **Evidence** | Path + line span + extractor/version ([§6](#6-provenance-contract)) | Path-only evidence (today's `evidence: [file_path]`) | Path-only cannot cite *where* in a file, cannot be validated against a revision, and cannot support #95's navigable claims. |
| **Legacy facts** | Retain as `legacy_unverified`, supersede by reanalysis ([§10.3](#103-legacy-regex-intelligence)) | Auto-migrate regex facts into the graph as `observed` | Regex facts have no spans and no extractor provenance; labeling them `observed` would be exactly the fabricated certainty this contract exists to prevent. |
| **Unresolved relationships** | Diagnostic, never a stored edge ([§5.5](#55-unresolved-relationships)) | Emit a best-guess edge | A guessed edge presented as fact destroys trust; #91 treats a false `observed` edge as release-blocking. |
| **Schema versioning** | Per-snapshot version, retained forever ([§9.6](#96-historical-snapshots-retain-their-version)) | One global mutable schema version | A global version cannot describe historical snapshots; immutable artifacts must carry the version they were built under. |
| **Occurrences** | One edge, multiple evidence ([§5.4](#54-multiple-occurrences-and-multiple-evidence)) | One edge per occurrence (parallel edges) | Parallel edges complicate canonicalization and de-dup with no consumer benefit; "does A call B?" is answered once, with citations. |
| **Columns** | Deferred to v2, reserved ([§6.2](#62-line-and-span-rules-decided-not-optional)) | Require columns in v1 | Line granularity is enough to prove the model end-to-end (#95); columns add extractor cost and hash surface without being needed for v1's acceptance bar. |
| **Duplicate/anonymous symbol discriminator** | Revision-local source-order ordinal ([§4.1](#41-principle-and-cross-revision-guarantees)) | Content-based semantic discriminator (signature/body hash) for cross-revision identity | The ordinal is cheap and deterministic within a revision; the semantic discriminator raises extractor cost/complexity (#89/#90) for a cross-revision benefit no v1 criterion needs, and would be a breaking `ri.v2` key change. Deferred, with evidence-comparison as the interim path. |
| **`derived_from` reference** | Same-snapshot tagged observation/node/edge/assertion references ([§6.4](#64-observations-and-the-derived_from-reference-model)) | Observation-only flattening, database ids, placeholders, or free text | Tagged canonical identities preserve immediate resolved/inferred dependencies and allow recursive tracing to source evidence; pre-seal resolution and cycle detection keep the chain valid. |
| **Pipeline identity** | Precomputed planned `producer_version_set` ([§3.3](#33-snapshot-identity)) | Record only producers discovered to have participated | Post-execution participation cannot support idempotent lookup before enqueue and omits enabled classifiers that legitimately produce no output on a particular revision. |
| **Canonical ordering** | Semantic tuple plus complete JCS bytes as final tie-breaker ([§12.3](#123-total-ordering-and-deduplication)) | Partial tuples with insertion order deciding ties | Partial tuples allow unequal evidence/diagnostics to compare equal. Complete bytes make ordering total and reproducible. |
| **Empty text files** | One logical empty line; whole-file evidence `1..1` ([§6.2](#62-line-and-span-rules-decided-not-optional)) | Treat as zero lines or make whole-file evidence invalid | A single exact convention keeps empty-file provenance valid and benchmarkable while binary/undecodable inputs remain explicit diagnostics. |

### 15.1 Operational costs and limitations (stated honestly)

- **Storage grows per revision.** Immutable snapshots mean re-analysis stores a new graph rather
  than overwriting. This is the deliberate cost of reproducibility; retention/pruning policy is out
  of scope for this RFC and will be its own issue.
- **Reanalysis is required to benefit from a better extractor.** Because facts are never upgraded in
  place ([§7.3](#73-upgrades-retention-labeling)), an improved extractor helps only new snapshots
  until old repositories are re-analyzed.
- **Determinism constrains producers.** Extractors, resolvers, and classifiers must be deterministic and must not
  embed timestamps, absolute paths, or nondeterministic ordering, or the canonical hash
  ([§12](#12-canonical-graph-hash)) destabilizes. This is a real implementation constraint on #89–#91.
- **`ri.v1` is line-granular only.** No columns, no cross-file type inference beyond documented
  resolution, no non-TS/Python deep extraction. These are declared gaps, not hidden ones, consistent
  with [REPOSITORY_INTELLIGENCE.md](REPOSITORY_INTELLIGENCE.md).
- **Duplicate/anonymous symbol identity is revision-local.** The `#<n>` and `(anonymous:…#<ordinal>)`
  discriminators are assigned by source order, so they are stable within a revision but do not track
  the same entity across revisions ([§4.1](#41-principle-and-cross-revision-guarantees)). The
  considered-but-**deferred** alternative is a **content-based semantic discriminator** — hashing a
  normalized signature (parameter arity/types for overloads, a normalized body digest for anonymous
  symbols) instead of a source-order ordinal. It was deferred from `ri.v1` because it materially
  raises extractor cost and language-specific complexity (#89/#90) for a benefit — cross-revision
  matching of duplicate/anonymous symbols — that no v1 acceptance criterion requires; consumers that
  need it use evidence (path + span) comparison in the interim. Introducing it later is a breaking
  key-format change and therefore an `ri.v2` concern ([§9.2](#92-breaking-changes-require-riv2)).
- **This RFC changes no runtime behavior.** The system behaves as documented today until each
  downstream implementation lands; this document records the *accepted contract*, not a claim that
  every capability is current behavior.

---

## 16. Dependency gate

This RFC records the exact sequencing rule for the intelligence track (the comment on #86 is
binding). The governance gate now has the required independent approval, and this final pre-merge
update records that approval in the contract:

- **#87, #88, #89, #90, #91, #92, #93, and #95 may proceed against the accepted contract**, while
  continuing to honor the dependency order below and their own acceptance criteria.
- **#94 fixture construction was permitted before approval** — writing expected facts down first is
  a genuine test of whether the support matrix is coherent.
- **#94 scoring and provenance validation depend on the accepted contract** (they need the
  evidence-record definition in [§6](#6-provenance-contract) and the canonical hash in
  [§12](#12-canonical-graph-hash)).
- **Contract acceptance and implementation status are distinct.** Approval permits downstream work;
  it does not make that work current product behavior. PR #102 implemented #87/#88, and PR #103
  implemented the standalone #89/#90 extractors. Product orchestration and consumer migration
  remain separate downstream work.

Dependency order (from the #86 comment): #87 → #88 → {#89, #90} → #91 → #92 → #93 (on #88); #94 in
parallel (fixtures early, scoring after approval); #95 last (on #92 and #94).

---

## 17. Current behavior vs. accepted contract vs. implementation status

To keep this document honest about what exists (per [docs/README.md](../README.md) documentation
rules), the three columns are explicit:

| Concern | Current behavior (today) | Accepted `ri.v1` contract (this RFC) | Status |
| --- | --- | --- | --- |
| Storage | Legacy regex consumers still read the mutable JSON blob; normalized snapshot tables and the sealing store now exist | Immutable sealed snapshots with nodes, edges, assertions, observations, evidence, and diagnostics (§11) | **Persistence implemented** (#88); production producers/queries remain #89–#92 |
| Pipeline identity | Durable submission and execution share a fixed planned producer set and config hash before enqueue | Precomputed `producer_version_set` covers every enabled extractor/resolver/classifier (§3.3) | **Implemented** (#88/#93) |
| Repository graph key | Durable analysis runs `ExtractionPipeline`, which emits deterministic `repo:root`; `SnapshotStore` validates exactly one before sealing | Deterministic snapshot-scoped `repo:root`; database `repository_id` excluded from graph keys (§4.3) | **Implemented** (#88–#90/#93) |
| Symbol spans | Python/TypeScript extractors emit and durable analysis stores required spans; legacy `SourceSymbol` remains spanless | Required line spans (§6) | **Producer and durable population implemented** (#89/#90/#93) |
| Extraction | Durable analysis runs the AST/tree-sitter extractors and also preserves the legacy regex model for unmigrated consumers | Syntax-aware extractors with support matrices | **Durable product integration implemented** (#89/#90/#93) |
| Revision identity | Indexed `revision_kind`/`revision_value`/`revision_ref`; `commitSha` is API compatibility only | Indexed immutable columns (§3) | **Implemented** (#87) |
| Relationships | The durable job runs the deterministic resolver over stored observations, with resolved edges and explicit unresolved/ambiguous diagnostics | Resolved edges + diagnostics (§5) | **Implemented** (#91/#93) |
| Inferred entity properties | Legacy heuristic module roles remain in the compatibility blob; the snapshot store supports separate validated assertions | Separate inferred property assertions; observed nodes remain unique (§5.6) | **Persistence implemented** (#88); production inference/querying remains #91/#92 |
| Provenance | Durable analysis stores extractor path + span + producer/version and the normalized store validates them; legacy product consumers still receive file paths only | Path + span + extractor/version (§6) | **Producer, persistence, querying, and durable population implemented** (#88–#93) |
| Query API | Normalized consumers use the versioned owner-scoped read API; legacy consumers still read the compatibility blob | Versioned owner-scoped read API (§9.5) | **Implemented and durably populated** (#92/#93); broader consumer migration remains #95 |
| Evidence-backed output | AI emits empty citation lists | Every claim cites a valid span (§7.4) | **Unimplemented** (#95) |

**This RFC does not claim every capability in the "Accepted contract" column is current product
behavior.** RFC-0001 is **Accepted** — independently ratified by
[@SHAURYAKSHARMA24](https://github.com/SHAURYAKSHARMA24) on 2026-07-16
([§1](#1-status-and-approval)); acceptance records the governing contract, not a claim of
implementation. The #87 revision identity and #88 immutable snapshot-persistence boundary are
implemented against that accepted contract, as the status column records. The #89/#90 producers
and #94 benchmark plus #91 deterministic resolution, #92 sealed-snapshot queries,
and #93 durable job population are implemented; broader consumer migration
remains downstream work. No existing documentation is rewritten by
this RFC to imply otherwise.

---

## 18. Decision matrix — acceptance criteria and dependency requirements → RFC section

### 18.1 Issue #86 acceptance criteria

| #86 acceptance criterion | Satisfied by |
| --- | --- |
| Node/edge identity (stable-key format) specified; assertion identity also specified | [§4](#4-node-identity-and-stable-keys), [§5](#5-edgefact-identity) |
| Provenance record specified: path, start line, end line, extractor, extractor version | [§6.1](#61-the-evidence-record), [§6.2](#62-line-and-span-rules-decided-not-optional) |
| Truth classes defined, with rules for which extraction paths may emit each | [§7](#7-truth-classes), emission matrix [§7.2](#72-emission-matrix-producer--truth-class) |
| Schema versioning and migration policy specified | [§9](#9-schema-versioning), [§10](#10-migration-policy) |
| Immutability rules for completed snapshots specified | [§11](#11-snapshot-lifecycle-and-immutability) |
| Diagnostics model (unsupported construct, ambiguous resolution, extraction failure) specified | [§8](#8-diagnostics-model) |
| Accepted as an ADR/RFC with recorded independent-maintainer approval | [§1](#1-status-and-approval) — approved by [@SHAURYAKSHARMA24 in Issue #86](https://github.com/Second-Origin/PARTHA/issues/86#issuecomment-4990687780) and in the [PR #101 review](https://github.com/Second-Origin/PARTHA/pull/101#pullrequestreview-4712687647) on 2026-07-16 |

### 18.2 Required RFC decisions (issue body §1–§15) and #86-comment dependency requirements

| Requirement | RFC section |
| --- | --- |
| 1. Status/number/issue/authors/dates/status/approval rule | [§1](#1-status-and-approval) |
| 2. Normative terminology (MUST/…); snapshot, fact, node, edge, assertion, observation, evidence, provenance, diagnostic, producer, schema/producer version | [§2](#2-normative-terminology) |
| 3. Revision & snapshot identity (git SHA + ref; upload sha256; moving names; precomputed planned producer set; composite identity; reanalysis; reuse; #87 migration) | [§3](#3-revision-and-snapshot-identity) |
| 4. Node identity & stable keys (`repo:root`; snapshot uniqueness; all node types; path normalization; `.`/`..`; symlinks/escape; case; Unicode; qualified/nested/overloads/anonymous; language namespace; external deps; collisions; TS/Python examples) | [§4](#4-node-identity-and-stable-keys) |
| 5. Edge/assertion identity (relationship and assertion predicates; subject/object/value; deterministic IDs; snapshot scope; unique entity nodes; multiple evidence; ordering/dedup; #91 relationships) | [§5](#5-edgefact-identity) |
| 6. Provenance contract (min record; logical line count and empty files; one-based inclusive spans; binary/undecodable behavior; whole-file; columns deferred; multiple evidence; tagged acyclic derivation; revision tie; no provenance ⇒ not observed) | [§6](#6-provenance-contract) |
| 7. Truth classes (definitions; producers; no upgrade; retention; API/UI labeling; generated never stored; unresolved ⇒ diagnostic; emission matrix) | [§7](#7-truth-classes) |
| 8. Diagnostics model (all listed categories; required fields; which fail a snapshot) | [§8](#8-diagnostics-model) |
| 9. Schema versioning (accepted `ri.v1`; compatible additions; breaking; when v2; schema vs producer version; API versioning #92; reader rejection/negotiation; historical retention) | [§9](#9-schema-versioning) |
| 10. Migration policy (DB migrations; backfills; rollback; cross-version; re-extraction vs transformation; legacy regex facts; failure/recovery) | [§10](#10-migration-policy) |
| 11. Snapshot lifecycle & immutability (states; seal transaction; producer coverage; entity uniqueness; derivation resolution/cycle rejection; total-order normalization; immutability; rejection; corrections ⇒ new snapshot; failed; #93 cancel/retry; concurrency/idempotency) | [§11](#11-snapshot-lifecycle-and-immutability) |
| 12. Canonical graph hash (five arrays; planned producer inputs; total ordering with JCS tie-breakers; evidence/derivation/property ordering; diagnostics/details; excluded volatile ids; determinism) | [§12](#12-canonical-graph-hash) |
| 13. Security & ownership (owner-scoped queries; no traversal; repo-relative paths; no secret/content logging; no working-tree reads; no independent parsers) | [§13](#13-security-and-ownership) |
| 14. Examples (all ten required) | [§14](#14-normative-examples) |
| 15. Alternatives & consequences (all six listed; operational costs) | [§15](#15-alternatives-and-consequences) |
| Dependency gate (accepted contract governs #87–#93 and #95; #94 fixtures were permitted early; #94 scoring uses the accepted contract) | [§16](#16-dependency-gate) |
| #87 — revision identity & migration of `commitSha` | [§3.2](#32-revision-identity), [§3.5](#35-migration-of-the-existing-commitsha-handled-by-87) |
| #88 — immutable snapshot persistence, node/edge/assertion uniqueness & canonical hash | [§4.1](#41-principle-and-cross-revision-guarantees), [§5.6](#56-inferred-property-assertions), [§11](#11-snapshot-lifecycle-and-immutability), [§12](#12-canonical-graph-hash) |
| #89 — TypeScript extraction (spans, stable keys, support matrix, diagnostics) | [§4](#4-node-identity-and-stable-keys), [§6](#6-provenance-contract), [§7.1](#71-definitions-and-emission-rules), [§8](#8-diagnostics-model) |
| #90 — Python extraction (decorators/routes, spans, shared interface) | [§4](#4-node-identity-and-stable-keys), [§6](#6-provenance-contract), [§8](#8-diagnostics-model), example [§14.2](#142-observed-python-function-with-a-decorator) |
| #91 — deterministic relationship resolution (contains/defines/imports/calls/routes_to/depends_on/implements; immediate producer; tagged derivation; resolved class; diagnostics) | [§5.1](#51-canonical-predicates), [§5.5](#55-unresolved-relationships), [§6.4](#64-observations-and-the-derived_from-reference-model), [§7](#7-truth-classes) |
| #92 — versioned owner-scoped query API for nodes, edges, assertions, derivations & evidence | [§5.6](#56-inferred-property-assertions), [§9.5](#95-api-response-versioning-92-and-negotiation), [§13](#13-security-and-ownership) |
| #93 — durable job lifecycle & snapshot sealing | [§11.2](#112-sealing-transaction-and-pre-seal-validation), [§11.4](#114-failed-extraction-cancellation-retry-93-interaction), [§11.5](#115-concurrency-and-idempotency) |
| #94 — golden benchmark (logical-line/empty-file vectors, provenance validity, total canonical ordering & hashing) | [§6.2](#62-line-and-span-rules-decided-not-optional), [§6.3](#63-multiple-evidence-resolvedinferred-evidence-and-the-revision-tie), [§12](#12-canonical-graph-hash), [§16](#16-dependency-gate) |
| #95 — first evidence-backed consumer | [§7.4](#74-generated-narrative), [§13](#13-security-and-ownership), example [§14.10](#1410-generated-narrative--explicitly-excluded-from-deterministic-facts) |

---

## 19. References

- [`apps/backend/app/intelligence/models.py`](../../apps/backend/app/intelligence/models.py) — current serialized model; `SourceSymbol` has no span.
- [`apps/backend/app/intelligence/engine.py`](../../apps/backend/app/intelligence/engine.py) — current regex extraction.
- [`apps/backend/app/parsers/tree_sitter_parser.py`](../../apps/backend/app/parsers/tree_sitter_parser.py) — placeholder parser (returns no symbols).
- [`apps/backend/app/services/repository_service.py`](../../apps/backend/app/services/repository_service.py) — `_metadata_with_intelligence`, `_content_hash_for_upload`, and service use of the owner-scoped repository accessor.
- [`apps/backend/app/repositories/repository_repository.py`](../../apps/backend/app/repositories/repository_repository.py) — owner-scoped `RepositoryRepository.get_for_owner`.
- [`apps/backend/app/github/client.py`](../../apps/backend/app/github/client.py) — `read_head_commit` (`git rev-parse HEAD`).
- [Repository Intelligence](REPOSITORY_INTELLIGENCE.md) — current deterministic-vs-heuristic behavior; the informal ancestor of the truth classes.
- [System Overview](SYSTEM_OVERVIEW.md) — current components, persistence, trust boundaries.
- [docs/README.md](../README.md) — documentation rules.
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — contribution workflow, migrations, architectural rules.
- Issues [#86](https://github.com/Second-Origin/PARTHA/issues/86) (this RFC) and [#87](https://github.com/Second-Origin/PARTHA/issues/87)–[#95](https://github.com/Second-Origin/PARTHA/issues/95) (downstream track).
