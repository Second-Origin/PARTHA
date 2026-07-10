# Definition of Ready & Definition of Done

Two checklists that gate work into and out of the sprint. Extracted from
[`PRODUCTION_READINESS_PLAN.md`](./PRODUCTION_READINESS_PLAN.md) §2.6 so they can be
referenced directly from an issue or a pull request.

- **Definition of Ready (DoR)** gates an issue *into* the sprint — it decides when an
  issue may be labeled `ready` and assigned.
- **Definition of Done (DoD)** gates a pull request *out* — it decides when a PR may
  merge to `dev`.

These complement, and do not replace, [`CONTRIBUTING.md`](../../CONTRIBUTING.md) and the
[pull request template](../../.github/pull_request_template.md). Where the PR template
asks "did you?", this document defines what a correct answer looks like.

---

## Definition of Ready

An issue is `ready` — assignable, and pullable into a sprint — when **all** of the
following are true. Anything unchecked means the issue is still `needs-design` or
`blocked`, not `ready`.

- [ ] **Clear acceptance criteria.** The issue states what must be true for it to be
      closed, in terms someone other than the author can verify. Not "improve
      parsing" but "parser emits an edge for every resolved import; test proves it."
- [ ] **Area is set.** Exactly one of `area/backend`, `area/frontend`, `area/ai`,
      `area/infra`, `area/db`, `area/docs` (§2.3).
- [ ] **Priority is set.** `P0`–`P3`.
- [ ] **Milestone is set.** One of `M1 — Foundations`, `M2 — Real Intelligence`,
      `M3 — Operate It`, `M4 — Launch Polish` (§2.2).
- [ ] **Dependencies are linked.** Blocking issues are referenced, and the issue
      carries `blocked` if any of them are still open.
- [ ] **Design is agreed** — required if the work touches **API shape, persistence, or
      security**. The decision, and the alternatives rejected, live in a comment on the
      issue itself, so the trail is readable by whoever picks it up next.

> Issue type (Epic / Feature / Task / Bug) is a native GitHub issue type, not a label
> (§2.1). Sub-issues inherit their parent's Project and Milestone automatically.

### Ready in one line

> Someone who did not write this issue could pick it up, know when they are finished,
> and know who to ask about the one decision that was already made.

---

## Definition of Done

A pull request may merge to `dev` when **all** of the following are true.

### Correctness

- [ ] **Acceptance criteria met.** Every criterion on the linked issue is satisfied. If
      one was dropped or changed, the issue is updated to say so — silently shipping a
      narrower scope than the issue promised is not done.
- [ ] **Tests added or updated.** New behavior gets a test; changed behavior gets its
      test changed. A bug fix gets a test that fails without the fix.
- [ ] **CI is green.** The `Frontend`, `Backend`, and `Docker Compose` jobs pass. Once
      branch protection lands (§2.5), CodeQL and Dependabot join them as required
      checks.

### Code quality

- [ ] **No new `any` in TypeScript.** If a type is genuinely unknown, use `unknown` and
      narrow it. An `any` that must ship carries a comment explaining why.
- [ ] **No new broad `except:` in Python.** Catch the exception you can actually handle.
      A bare or `except Exception:` clause that must ship re-raises or logs with context,
      and says why it is broad.

### Documentation & safety

- [ ] **Docs updated if behavior changed.** API shape, env vars, setup steps, and
      operational runbooks. If a reader of the docs would now be wrong, the docs change
      in the same PR.
- [ ] **No secrets committed.** No API keys, tokens, `.env` files, credentials, or
      local databases — in the diff or anywhere in the branch's history.
- [ ] **No build artifacts committed.** No `dist/`, no `*.tsbuildinfo`, no
      `__pycache__/`, no coverage output.

### Reachability

- [ ] **The feature is reachable through the UI**, or it is **explicitly documented as
      internal**. Backend capability that no user can reach, and that no document
      admits is internal-only, is not done — it is a half-finished feature that reads as
      a finished one.

### Done in one line

> The acceptance criteria hold, CI proves it, a reader of the docs would not be misled,
> nothing secret or generated is in the diff, and a user can actually get to it.

---

## Applying this

- **Weekly planning** (§2.7) is where issues are triaged against the DoR and labeled
  `ready`. An issue that fails the DoR is not "almost ready" — it goes back with the
  missing piece named.
- **Review** is where the DoD is enforced. A reviewer may block on any unchecked box.
- Keep PRs under **~400 lines of diff** (§2.7). A PR too large to review against this
  checklist is too large to merge; split the epic into task-sized PRs.
- PRs touching `core/`, auth, or migrations require **two** approving reviews (§2.5).

## See also

- [`PRODUCTION_READINESS_PLAN.md`](./PRODUCTION_READINESS_PLAN.md) — milestones (§2.2),
  labels (§2.3), ownership (§2.4), branch protection (§2.5), cadence (§2.7).
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — branch strategy, Conventional Commits,
  squash merge, issue-assignment flow.
- [`.github/CODEOWNERS`](../../.github/CODEOWNERS) — who reviews which area.
