# CORE 1 Ingestion Pipeline Audit

Issue: GitHub Issue #11, CORE 1 — End-to-End Repository Ingestion & Analysis Pipeline
Date: 2026-07-08
Branch: `feature/core-1-repository-ingestion`

## Scope

This audit traces the complete repository ingestion path:

```text
Frontend Upload UI
-> Upload Hooks
-> Repository API Client
-> FastAPI Routes
-> Repository Service
-> GitHub Clone / ZIP Extraction
-> Repository Parser
-> Repository Storage
-> Analysis Pipeline
-> Repository Intelligence
-> Frontend Repository State
```

The objective was stabilization, not feature expansion. Fixes were made incrementally and preserve the existing frontend/backend architecture.

## Executive Summary

The ingestion pipeline was functional for happy-path uploads, but it mixed real backend work with frontend-owned state transitions. The most serious failure was that the frontend forced imported repositories into an `analysing` state even when the backend had already returned a different state. Backend errors were also flattened into generic messages, and some repository API calls swallowed failures entirely.

The backend also marked imports as fully `completed` immediately, while `/analysis/{id}/start` only stamped completion metadata. This made the lifecycle misleading and prevented users from trusting the analysis screen.

This pass fixes the highest-risk issues without introducing a large rewrite:

- backend duplicate detection for uploads and GitHub imports;
- meaningful conflict, timeout, validation, and backend error responses;
- enforced Git clone timeout using subprocess execution;
- archive cleanup on failed imports;
- empty archive rejection;
- safer tar handling for links/devices;
- backend-owned `analysing -> completed/error` analysis state;
- frontend error messages now surface backend response messages;
- repository provider no longer hides backend load failures;
- upload/GitHub hooks no longer fabricate local `analysing` state;
- frontend refreshes repository state from the backend after analysis starts;
- cancel no longer deletes a repository from local state.

## Pipeline Audit Table

| Component | Current behaviour before fixes | Expected behaviour | Root cause | Severity | Recommended fix | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Upload page | Accepted file/GitHub input and navigated to analysis page after hook success. | Navigate according to backend repository state. | Page assumed every import should show analysis progress. | Medium | Route completed repositories to detail; only show analysis page for backend `analysing` state. | Fixed |
| `useUpload` | Uploaded file, called analysis start, then overwrote backend response with local `status: analysing`. | Store only backend-returned repository state. | Frontend simulated lifecycle after backend response. | High | Start backend analysis, fetch repository, store refreshed backend state. | Fixed |
| `useGitHubImport` | Same local `analysing` override after GitHub import. | Store only backend-returned repository state. | Duplicate local state transition. | High | Start backend analysis, fetch repository, store refreshed backend state. | Fixed |
| Repository API client errors | Backend `message` fields were ignored for common statuses such as 422. | Display backend validation/conflict/clone messages. | `getErrorMessage` returned generic status strings before inspecting body. | High | Prefer backend `body.message`; retain network/timeout fallbacks. | Fixed |
| Backend facade `fetchRepositories` | Returned `[]` on any backend failure. | Distinguish empty repository list from failed request. | Catch-all swallowed API/network errors. | High | Let errors propagate to RepositoryProvider. | Fixed |
| Backend facade `fetchRepository` | Returned `null` on any backend failure. | Preserve backend error semantics. | Catch-all swallowed API/network errors. | Medium | Let errors propagate. | Fixed |
| Backend facade `deleteRepository` | Returned `false` on any delete failure. | Surface deletion failure. | Catch-all swallowed API/network errors. | Medium | Let errors propagate; page displays action error. | Fixed |
| RepositoryProvider | Always exposed `loading: false`, `error: null`, no retry. | Expose loading/error/retry from backend fetch. | Provider did not model request state. | High | Add loading, error, and refresh state. | Fixed |
| Repository store | `addRepository` appended records blindly. | Upsert by repository id. | Frontend could duplicate repository state. | Medium | Make `addRepository` idempotent/upsert. | Fixed |
| Local cancel analysis | Removed repository from local store only. | Do not mutate repository state without backend confirmation. | Cancel was a frontend-only simulation. | High | Cancel viewing only; preserve repository. | Fixed |
| Upload route | Accepted archive but ignored extra form fields. | Import archive and persist parsed repository. | Name is derived server-side; extra fields are currently not part of backend contract. | Low | Keep contract; use server-derived name. | Accepted |
| GitHub route | Cloned synchronously with GitPython and no enforced timeout. | Clone must have bounded execution and clear failure messages. | `clone_timeout_seconds` was stored but unused. | High | Use `git clone` subprocess with timeout and cleanup. | Fixed |
| GitHub malformed URLs | Rejected non-GitHub HTTPS URLs. | Reject malformed/non-GitHub URLs with 422. | Backend URL validation exists. | Low | Keep validation. | Working |
| GitHub branch input | Branch was passed directly to clone. | Validate branch syntax before clone. | Missing branch validation. | Medium | Add conservative branch name validation. | Fixed |
| GitHub private/invalid repos | Clone failure returned generic external error with stderr. | Return clear public/branch failure message. | Git provider failures were not normalized. | Medium | Return 502 with actionable message. | Fixed |
| Duplicate GitHub import | Duplicate URL could create duplicate repository records. | Detect duplicate URL/branch. | No repository lookup before clone. | High | Add `find_by_source` and return 409 conflict. | Fixed |
| Duplicate archive upload | Frontend checked names, backend did not. | Backend is source of truth for duplicate detection. | Validation existed only in hooks. | High | Add `find_by_name` and return 409 conflict. | Fixed |
| ZIP upload | Happy path worked. | Parse, persist, and expose analysis state. | Baseline path was functional but completion state was misleading. | Medium | Persist as `analysing` after parse; complete through analysis endpoint. | Fixed |
| TAR.GZ upload | Supported by `tarfile.is_tarfile`. | Supported and tested. | No integration test existed. | Medium | Add TAR.GZ integration test. | Fixed |
| Invalid archive | Returned unsupported archive validation for non-archive bytes. | Return meaningful 422. | Basic validation existed. | Low | Add regression test. | Fixed |
| Corrupted archive | Some extraction errors were not normalized. | Return meaningful 422 and cleanup. | Missing extraction exception handling. | Medium | Catch extraction errors and cleanup. | Fixed |
| Empty archive | Could persist an empty completed repository. | Reject empty repositories. | Parser allowed zero files. | High | Validate parsed file count before record creation. | Fixed |
| Large upload | Storage enforces max size while streaming. | Reject over configured max size. | Existing chunked size guard. | Low | Keep; add future explicit test. | Partially covered |
| Tar links/devices | Path traversal checked but links/devices were not rejected. | Reject unsafe tar member types. | Tar extraction trusted member types. | Medium | Reject symlinks, hardlinks, and device entries. | Fixed |
| Upload cleanup | Failed imports could leave extracted directories or uploaded archives. | Failed imports should not leave partial artifacts. | No cleanup on exception. | Medium | Delete upload and repository path on failure. | Fixed |
| Repository parser | Builds file tree and metadata. | Parse once and provide repository intelligence. | Parser is heuristic but functional. | Medium | Keep parser as single source; improve AST depth later. | Remaining |
| Repository persistence | Records saved and listable. | Repository visible after refresh and reusable. | Happy path worked; duplicate policy missing. | High | Add duplicate checks and refreshed frontend state. | Fixed |
| Analysis start | Stamped repository completed without running analyzers. | Execute analysis work and persist completed/error state. | Mocked lifecycle. | High | Run architecture/dependency/review builders before completion. | Fixed |
| Analysis status | Reflected stored record state. | Report backend-owned state. | Status was only as truthful as stored lifecycle. | High | Store meaningful `analysing/completed/error` transitions. | Fixed |
| Analysis cancellation | No backend endpoint. | Do not fake cancellation. | Frontend-only local deletion. | High | Remove destructive local cancel behavior. | Fixed; backend cancel remains missing |
| Repository refresh | Provider loaded list on startup. | Refresh should preserve backend truth or show error. | Fetch failures were hidden. | High | Add provider loading/error/retry. | Fixed |

## API Audit

| Endpoint | Response codes observed/expected | Failure handling | State consistency | Status |
| --- | --- | --- | --- | --- |
| `GET /repositories` | `200` on success. | Previously frontend swallowed failures. | Now provider surfaces request failures. | Fixed frontend handling |
| `GET /repositories/{id}` | `200` on success, `404` when missing. | Backend emits structured `not_found`. | Frontend no longer converts all failures to `null`. | Fixed frontend handling |
| `DELETE /repositories/{id}` | `204` on success, `404` when missing. | Backend emits structured errors. | Frontend no longer silently ignores delete failures. | Fixed frontend handling |
| `POST /repositories/upload` | `201` success, `409` duplicate, `422` invalid/empty/unsafe archive. | Structured backend messages are surfaced by frontend. | Failed imports do not create repository records. | Fixed |
| `POST /repositories/github` | `201` success, `409` duplicate, `422` malformed URL/branch, `502` clone failure, `504` clone timeout. | Clone failures and timeouts are normalized. | Failed imports clean repository path. | Fixed |
| `POST /analysis/{id}/start` | `200 completed` on success/idempotent completed, `200 failed` if already error, `404` missing. | Analyzer exceptions set repository `error` and raise service error. | No longer blind completion stamping. | Fixed |
| `GET /analysis/{id}/status` | `200` with `processing/completed/failed`, `404` missing. | Uses stored repository state. | Reflects backend-owned status/progress. | Fixed |
| `GET /analysis/{id}/architecture` | `200`, `404` missing. | Existing behavior. | Builds on parsed repository. | Unchanged |
| `GET /analysis/{id}/dependencies` | `200`, `404` missing. | Existing behavior. | Builds on parsed repository. | Unchanged |
| `GET /analysis/{id}/review` | `200`, `404` missing. | Existing behavior. | Builds on parsed repository. | Unchanged |

## Frontend Audit

| Area | Finding | Root cause | Fix |
| --- | --- | --- | --- |
| Generic “No Internet Connection” style errors | Backend validation/conflict messages were replaced by generic strings. | API error formatter ignored backend `message`. | `getErrorMessage` now prefers backend messages. |
| Empty repository page on backend failure | `fetchRepositories` returned `[]` for any failure. | Catch-all in backend facade. | Errors now propagate; provider exposes error/retry. |
| Upload fake state | Hooks set `status: analysing` locally after backend response. | Frontend duplicated backend lifecycle. | Hooks fetch backend repository after analysis start and store that state. |
| Fake progress screen | Upload always navigated to `/analysis/:id`. | UI assumed an in-progress lifecycle even when backend completed. | Upload page routes completed repos to detail. |
| Fake cancel | Cancel removed local repository only. | No backend cancel endpoint. | Cancel now leaves repository state intact and navigates back. |
| Duplicate local repository records | Store appended every imported repository. | No idempotent upsert. | `addRepository` now upserts by id. |

## Repository Lifecycle Verification

| Transition | Before | After |
| --- | --- | --- |
| Repository created | Created after parsing; no duplicate guard. | Created after parsing and duplicate validation. |
| Repository stored | Stored as `completed` immediately. | Stored as `analysing` with parsed file tree and metadata. |
| Repository parsed | Parser ran during import. | Parser still runs once during import. Empty parse is rejected. |
| Analysis started | Frontend called start, backend stamped completed. | Frontend calls start, backend runs analyzers and persists completion/error. |
| Analysis completed | Completed state was partly mocked. | Completed only after analyzer execution returns. |
| Repository visible after refresh | Worked on success; backend fetch failure looked empty. | Success persists; failures show load error/retry. |
| Repository reusable | Completed records could be reused. | Completed records remain reusable; duplicate local state reduced. |

## Prioritized Bug List

| Priority | Bug | Status |
| --- | --- | --- |
| Critical | Frontend fabricated repository `analysing` state after backend response. | Fixed |
| Critical | Analysis start blindly stamped completed. | Fixed |
| High | Backend duplicate detection missing. | Fixed |
| High | Backend facade swallowed repository load/delete errors. | Fixed |
| High | Backend error messages hidden by generic frontend messages. | Fixed |
| High | GitHub clone timeout was configured but not enforced. | Fixed |
| High | Empty archives could become completed repositories. | Fixed |
| Medium | Failed uploads/clones left partial artifacts. | Fixed |
| Medium | Unsafe tar link/device entries were not rejected. | Fixed |
| Medium | Repository cancel deleted local state only. | Fixed |
| Medium | No backend cancellation endpoint. | Remaining |
| Medium | No async queue/worker for long-running imports and analysis. | Remaining |
| Medium | Parser and intelligence layer remain heuristic. | Remaining |

## Completed Fixes

- Added `ConflictServiceError` and `TimeoutServiceError` for precise API semantics.
- Added repository duplicate lookup by name and by source URL/branch.
- Enforced GitHub clone timeout with `subprocess.run(..., timeout=...)`.
- Added GitHub branch validation.
- Normalized clone failures and timeout responses.
- Rejected empty parsed repositories.
- Cleaned uploaded archives and extracted repository paths on failed imports.
- Rejected tar symlink, hardlink, and device members.
- Changed imports to persist `analysing` state after successful parsing.
- Changed analysis start to execute analyzers and persist `completed` or `error`.
- Added backend ingestion tests for ZIP, TAR.GZ, invalid archive, empty archive, duplicates, GitHub validation, and clone timeout.
- Updated frontend error handling to surface backend messages.
- Removed swallowed repository API failures from the frontend backend facade.
- Added RepositoryProvider loading/error/retry state.
- Removed frontend local fake `analysing` repository overrides.
- Refreshed repository state from backend after analysis start.
- Changed upload navigation to respect backend repository status.
- Removed destructive local-only analysis cancel behavior.

## Tests Added

New file: `apps/backend/tests/test_ingestion_pipeline.py`

Coverage includes:

- ZIP upload persists repository and completes analysis through `/analysis/{id}/start`.
- TAR.GZ upload is accepted and parsed.
- Invalid archive returns backend validation error.
- Empty archive is rejected.
- Duplicate upload returns `409` conflict.
- GitHub import duplicate detection and branch validation.
- GitHub clone timeout raises `TimeoutServiceError`.

## Remaining Issues

| Issue | Why it remains | Recommended next step |
| --- | --- | --- |
| No true async queue | Current architecture has no worker/job table. Long clone/analysis requests still block the request. | Introduce job records and worker-backed ingestion/analysis. |
| No backend cancel endpoint | There is no cancellable job abstraction yet. | Add cancellation once async jobs exist. |
| Progress is coarse | Backend progress is state-based, not event-streamed. | Emit real job stage transitions from worker. |
| File-content preview remains generated | Parser stores tree metadata, not safe file contents. | Add safe file content/indexing endpoint separately. |
| Dependency/architecture/review analyzers are heuristic | CORE 1 stabilizes ingestion, not analysis depth. | Continue under repository intelligence/knowledge graph issues. |
| Large repository scalability | Clone/upload parsing still happens in process. | Move heavy work to background workers with limits and retention. |

## Verification Commands

```bash
npm run test:backend
npm --prefix apps/frontend run lint
npm run build:frontend
```

All three commands passed after the fixes.
