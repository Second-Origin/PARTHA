# Versioning policy

PARTHA follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). This document
says what that means here: what counts as PARTHA's public API, what qualifies for a patch,
minor or major release, how the pre-1.0 period works, and the rules that keep the version
sequence honest. The mechanics of cutting a release (promote, verify, sync back, tag) are in
[CONTRIBUTING §14](CONTRIBUTING.md#14-releases); this file decides only **which number**.

Versions are written `MAJOR.MINOR.PATCH`, tagged `vMAJOR.MINOR.PATCH`, and are plain integers:
`0.9.0` is followed by `0.10.0`, not `1.0.0`.

## What is the public API

Semantic Versioning is only meaningful relative to a declared public API. PARTHA's is:

| Surface | What is covered |
| --- | --- |
| HTTP API | Routes, request and response shapes, status codes and error `code`s in the generated OpenAPI contract (`apps/frontend/src/shared/services/api/generated.ts` is checked against it in CI). |
| Configuration | Environment variables and their defaults and accepted values (`apps/backend/.env.example`, `docs/operations/`). |
| Operator tooling | The command-line interfaces of `apps/backend/scripts/` (`approve_email.py`, `cleanup_storage.py`, ...): names, flags, exit codes. |
| Upgrade path | That `alembic upgrade head` takes a database from any released version to the new one without manual steps, and what data a migration touches. |
| Exports | The structure of the JSON export and the report schema identifiers (`engineering-review.v2`, `repository-insights.v1`). |
| Snapshot schema | `ri.v1` has its own explicit schema version (RFC-0001). A change to it is governed by the RFC, and any incompatible change is at least a **minor** release before 1.0 and a **major** release after. |

**Not** public API, and free to change in any release: internal Python modules and function
signatures, database table layout beyond the upgrade guarantee above, frontend component
structure and styling, the wording of UI copy and log lines, CI, and the benchmark corpus.

## What qualifies for each bump

Decide by reviewing everything merged since the last tag and taking the **highest** level any
change reaches. A release that is mostly fixes but adds one new capability is a minor release.

### Patch: `0.3.0` -> `0.3.1`

Backward-compatible **bug fixes only**. Nothing a user or operator could describe as "new".

- Fixes that make the software do what its documentation already says.
- Security fixes that do not change the public API.
- Dependency updates that change no behaviour.
- Documentation and internal-only changes (refactors, tests, CI).
- A migration only when the fix requires it and it is data-only or corrective (for example,
  deleting a row a bad migration inserted). No new tables or columns.

A patch must **not**: add an endpoint, field, setting, flag, script or UI surface; change a
default; change what an existing response contains beyond correcting a wrong value; or need
any operator action beyond upgrading.

### Minor: `0.3.0` -> `0.4.0`

**New backward-compatible functionality**, or a change to existing behaviour that is visible
to users or operators.

- A new capability: for example Repository Lineage's read API and history page, a new export
  format, a new provider.
- New endpoints, response fields, settings, or script options.
- Additive migrations (new tables, columns, indexes).
- Deprecating something (it keeps working; the notes say what replaces it).
- Behaviour changes that are corrections in spirit but observable, such as a different set of
  Engineering Review findings or a changed timestamp format. Say so in the notes.

### Major: `1.x` -> `2.0.0`

**Incompatible changes** to the public API, after 1.0.

- Removing or renaming an endpoint, field, setting or script flag; changing what one means.
- A migration that needs manual steps, cannot run on the previous release's data, or discards
  data.
- Dropping a supported Python or Node version.
- An incompatible `ri.v1` change (a new schema version is introduced alongside; the old one is
  removed only in a major release).

## Before 1.0

SemVer item 4 says anything may change at any time while the major version is `0`. PARTHA
narrows that so that upgraders can still rely on the number:

- The middle number does the work of "major": **a breaking change bumps the minor version**
  (`0.3.0` -> `0.4.0`), and the release notes list it under a **Breaking** heading with what to
  do about it.
- The last number stays strictly **bug fixes** (the patch rules above apply unchanged), so
  `0.4.1` is always safe to take from `0.4.0`.
- Nothing before 1.0 is guaranteed stable across minor versions, which is why
  [SUPPORT.md](SUPPORT.md) says to read each release's notes before upgrading.

**1.0.0** is a promise, not a milestone: it declares the public API above stable and starts
enforcing the major rule. It will be cut when the maintainers judge that the HTTP API,
configuration and upgrade path are ones they are prepared to keep compatible, and it will say so.
There is no date or feature list attached to it.

## Rules that keep the sequence honest

1. **Increment by one, never skip.** Each release differs from the previous tag by exactly one
   step: the next patch (`0.3.1`), the next minor with patch reset (`0.4.0`), or the next major.
   The sequence `0.1.0, 0.1.1, 0.2.0, ..., 0.9.0, 0.10.0, ..., 1.0.0` is the expected shape.
2. **A published version is immutable.** Never delete, move or re-point a tag or replace a
   release's contents. A mistake is corrected by publishing the next version and saying so in its
   notes; a bad release may be marked in its own notes as superseded.
3. **One version everywhere.** The release commit sets the same number in `package.json`,
   `apps/frontend/package.json`, `apps/marketing/package.json` (and both `package-lock.json`
   files), `apps/backend/pyproject.toml` and the FastAPI `version=` in `apps/backend/app/main.py`,
   and version-bearing copy such as the marketing "Try PARTHA vX.Y.Z" button. Pull requests
   never change a version string.
4. **The notes justify the number.** Release notes group changes by area and state under a
   heading which of Security, Breaking, New or Fixes each belongs to, so a reader can check the
   bump against this policy.
5. **Pre-releases** use a SemVer pre-release suffix (`0.4.0-rc.1`), are marked pre-release on
   GitHub, and are never the target of the "latest" label.
6. **Ties go up.** If a change is arguably a patch and arguably a minor, it is a minor.

## Version history

| Version | Date | Kind | Note |
| --- | --- | --- | --- |
| `0.1.0` | 2026-07-09 | first release | The JavaScript packages still read `1.0.0` in this tag (an inconsistency, corrected in 0.2.0). |
| `0.2.0` | 2026-09-09 | minor | Sealed `ri.v1` snapshots, Repository Lineage, accounts. Versions aligned across all packages. |
| `0.3.0` | 2026-09-26 | minor | Reliability and truthfulness release (see the release notes). Published before this policy existed. It is not being re-cut. |

No release was skipped between these. There has not yet been a patch release; every release so far
has been cut when a batch of work was ready rather than by these rules, which is what this file
now settles.
