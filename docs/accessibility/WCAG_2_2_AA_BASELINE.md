# WCAG 2.2 AA accessibility baseline

This report establishes the reproducible Phase 0 accessibility baseline requested by
[#118](https://github.com/Second-Origin/PARTHA/issues/118). It deliberately separates automated
browser evidence from human and assistive-technology evidence. A green axe run is not a claim
that PARTHA conforms to WCAG 2.2 AA.

## Audit identity

| Field | Value |
| --- | --- |
| Original audit date | 2026-07-29 |
| Original source revision | `5bb63ca4e74882b0a08b5e8c761e1997590a5755` plus the issue #118 audit changes in this report's pull request |
| Operating system | Microsoft Windows NT 10.0.26200.0 |
| Latest automated revalidation | 2026-08-18 on the current source revision: 6/6 focused accessibility states and 22/22 full browser-acceptance journeys passed |
| Current source revision | `e4609f3db92de268f3c15f0dadb511d49995dd42` |
| Automated browser | Playwright Chrome for Testing 151.0.7922.34, headless Chromium project |
| Automated viewport | 1440 x 900 CSS pixels |
| Automated zoom | 100% browser zoom |
| Colour scheme | Repository default dark theme |
| Accessibility engine | axe-core 4.12.1 |
| Rule scope | `wcag2a`, `wcag2aa`, `wcag21aa`, and `wcag22aa` tags |

## Automated route and state coverage

The checked-in Playwright suite uses the same disposable account, SQLite database, storage
directory, and seven seeded repositories as the browser acceptance gate. It waits for
finite page animations to settle before running axe, so contrast measurements are not taken from
transient opacity frames.

| Journey | Route and selected state |
| --- | --- |
| Login | `/login`, initial sign-in form |
| Application shell/sidebar | authenticated dashboard, expanded desktop sidebar and top bar |
| Repository list | `/repositories`, seeded success list |
| Repository import | `/upload`, GitHub URL mode with an empty form |
| Architecture graph | `/architecture`, sealed `small` fixture with the graph rendered |
| Node/inspector | `/architecture`, first node selected and inspector dialog open |

Known violations are not disabled. Each exact rule/target/count is asserted against a stable test
identifier and linked issue. A new rule, a new target, or a changed count fails with the route,
state, rule, impact, offending markup, target selector, axe help URL, and failure summary. When a
follow-up fixes a violation, its exact expectation must be removed in the fixing pull request.

## Rerun instructions

From the repository root, install the locked frontend and backend development dependencies:

```text
npm ci --prefix apps/frontend
python -m venv apps/backend/.venv

# Windows
apps\backend\.venv\Scripts\python.exe -m pip install -r apps\backend\requirements-dev.txt
apps\backend\.venv\Scripts\python.exe -m pip install -e apps\backend --no-deps

# POSIX
apps/backend/.venv/bin/python -m pip install -r apps/backend/requirements-dev.txt
apps/backend/.venv/bin/python -m pip install -e apps/backend --no-deps
```

Install Chromium once if it is not already present, then run the focused or complete browser gate:

```text
npm --prefix apps/frontend exec -- playwright install chromium
npm run test:accessibility
npm run test:e2e
```

The runner chooses free loopback ports, uses the platform virtual environment when present, creates
fixture archives with Python's standard library, and removes its temporary database, repositories,
and fixture manifest after the run. Playwright filters can be forwarded for diagnosis, for example:

```text
node scripts/run-e2e-acceptance.mjs e2e/accessibility.spec.ts --grep "architecture graph"
```

CI runs `npm --prefix apps/frontend run test`, including the jsdom route smoke checks, and then
`node scripts/run-e2e-acceptance.mjs`, which includes this real-browser baseline.

## Manual and assistive-technology baseline

No interactive browser or screen reader was available for this audit. The entries below are
therefore **not tested manually**. Automated Playwright, DOM, accessibility-tree, and axe results
are not substituted for human or screen-reader evidence.

| Required check | Result | Exact human verification checklist |
| --- | --- | --- |
| Keyboard-only navigation | **Not tested manually** | With a fresh session, use only Tab, Shift+Tab, Enter, Space, arrows, and Escape through login, sidebar, repository list/import, graph, and inspector. Confirm every action is reachable and operable and no keyboard trap occurs. |
| Visible focus | **Not tested manually** | At every focus stop above, confirm a persistent, clearly visible indicator against adjacent colours, including graph nodes, menu triggers, row actions, import controls, and inspector sections. |
| Logical tab order | **Not tested manually** | Record the complete focus sequence for each route at desktop and narrow viewport. Confirm it follows reading order, does not enter hidden navigation, and returns sensibly after drawers/dialogs close. |
| 200% zoom and reflow | **Not tested manually** | At 1280 x 720 CSS pixels, set browser zoom to 200%. Confirm content reflows without two-dimensional page scrolling, clipping, overlap, or lost controls; pan inside the graph must not conceal an equivalent route to its information. |
| Contrast | **Not tested manually** | Use a calibrated contrast analyser on text, focus indicators, icons conveying state, controls, and graph/status colours in every selected state and supported theme. Record foreground/background values and ratios. axe automated findings are listed below but are not a complete manual contrast pass. |
| Reduced motion | **Not tested manually** | Enable the OS/browser `prefers-reduced-motion: reduce` setting before loading the app. Exercise navigation, menus, uploads, graph layout, and inspector transitions. Confirm non-essential motion is removed or reduced and no information depends on animation. |
| Screen-reader smoke test | **Not tested manually** | Record screen-reader name/version, browser/version, and OS. Verify page title/heading/landmarks; labelled login fields and errors; sidebar current page; repository table and row actions; upload mode and form; graph alternative; node inspector name, focus containment, sections, relationships, and close/return focus. |

The existing seeded architecture visual suite contains automated keyboard and narrow-viewport
assertions. Those checks are useful regression evidence, but they are not recorded as manual
results here.

## Manual validation close-out (2026-08-18)

This is a dated manual close-out confirmed by the maintainer on 2026-08-19. It does not replace
the historical **not tested manually** entries above and does not establish full WCAG 2.2 AA
conformance.

Environment: local seeded fixture app at `http://127.0.0.1:18081`, macOS 26.5.2, Google Chrome
152.0.7977.42. The browser was used as a normal desktop window; native Chrome zoom was reset to
100% after the 200% check. No application code was changed for this validation.

| Check | Route/state exercised | Result | Evidence and follow-up |
| --- | --- | --- | --- |
| Keyboard-only navigation | Login/auth screens; shell/sidebar and mobile drawer; repository list/upload; architecture graph and node inspector | **Pass — maintainer-confirmed** | On 2026-08-19 the maintainer confirmed complete Tab/Shift+Tab, Enter/Space, Escape, and arrow-key coverage across the required states, with no keyboard trap and disabled controls excluded from focus. |
| Focus visibility and restoration | Login, shell, drawer, overlays, dialogs, route changes, graph, and node inspector | **Pass — maintainer-confirmed** | On 2026-08-19 the maintainer confirmed visible focus indicators at each stop and correct focus containment/restoration after drawers, dialogs, overlays, inspector close, and route changes. |
| 200% zoom and reflow | Dashboard, `/repositories`, loaded `/architecture` graph, node inspector, and equivalent graph information route | **Pass — maintainer-confirmed** | On 2026-08-19 the maintainer confirmed native Chrome 200% reflow without unnecessary two-dimensional scrolling, clipping, overlap, or lost functionality; the graph alternative remained available. |
| Contrast | Text, focus indicators, icons, controls, graph/status colours, and selected states | **Pass — maintainer-confirmed** | On 2026-08-19 the maintainer confirmed the manual contrast review across the validated routes and selected states. Automated axe results remain supplemental and are not treated as a complete conformance claim. |
| Reduced motion | macOS Accessibility → Motion → Reduce motion; navigation, menus, upload, drawers/dialogs, graph, inspector, loading, and success | **Pass — maintainer-confirmed** | On 2026-08-19 the maintainer confirmed the required reduced-motion exercise completed with no information dependent on non-essential animation. The OS setting was restored afterward. |
| Screen-reader smoke test | Login, shell/sidebar, repository list, upload, graph alternative, and inspector | **Pass — maintainer-confirmed** | On 2026-08-19 the maintainer confirmed that macOS VoiceOver was enabled and exercised successfully in the real browser, with the tested experience working as expected and no defect reported. This result is based on direct maintainer confirmation; automated accessibility-tree output remains supplemental. |

No separate product-defect issue was filed from this pass: no product defect was confirmed.

## Confirmed violations and follow-up issues

| Route/state | Automated finding | WCAG 2.2 | Severity and impact | Follow-up |
| --- | --- | --- | --- | --- |
| ~~`/login`, initial form~~ | ~~Registration link relies on colour alone; axe reports `link-in-text-block` and 1.41:1 against surrounding copy.~~ | ~~1.4.1 Use of Color~~ | ~~Serious; the registration path can be missed by low-vision and colour-vision-deficient users.~~ | ~~[#240](https://github.com/Second-Origin/PARTHA/issues/240)~~ |
| ~~Authenticated shell~~ | ~~Notification and account icon buttons have no accessible names (`button-name`).~~ | ~~4.1.2 Name, Role, Value~~ | ~~Critical/high impact; screen-reader and voice-control users cannot identify persistent controls.~~ | ~~[#236](https://github.com/Second-Origin/PARTHA/issues/236)~~ |
| ~~`/repositories`, success list~~ | ~~Every open/delete icon action lacks a repository-specific accessible name (`button-name`).~~ | ~~4.1.2 Name, Role, Value~~ | ~~Critical/high impact; actions, including deletion, cannot be distinguished non-visually.~~ | ~~[#235](https://github.com/Second-Origin/PARTHA/issues/235)~~ |
| ~~Authenticated expanded sidebar~~ | ~~`More` section label is approximately 4.23:1 at 10px (`color-contrast`).~~ | ~~1.4.3 Contrast (Minimum)~~ | ~~Serious; the navigation grouping can be difficult to perceive.~~ | ~~[#238](https://github.com/Second-Origin/PARTHA/issues/238)~~ |
| ~~`/upload`, GitHub URL mode~~ | ~~Title, helper copy, field label, and URL placeholder can fall below 4.5:1 (`color-contrast`); the rebased Chromium run measured the title at 2.82:1 and placeholder at 2.87:1. axe 4.12 can omit individual targets across environments despite shared computed colors. The automated baseline therefore permits each exact known target up to its recorded count; a new target or increased count still fails.~~ | ~~1.4.3 Contrast (Minimum)~~ | ~~Serious; low-vision users can miss the import purpose, field purpose, public-URL constraint, or example format.~~ | ~~[#237](https://github.com/Second-Origin/PARTHA/issues/237)~~ |

**Resolved by #286** — repository open/delete actions now carry repository-specific accessible names (`Open <repository>` / `Delete <repository>`), and their icons are marked decorative.

**Resolved by the #289 sidebar regrouping** — the single `More` section label was replaced by the `Analysis` and `Assist` labels, rendered at full `text-muted-foreground` rather than `text-muted-foreground/70`, which clears 4.5:1 at that size. The element the #238 baseline was keyed to (`secondary-navigation-label`) no longer exists, so its automated allowance has been removed rather than left to silently permit a violation on an element that is gone.

**Resolved by the #118/#236/#237/#238/#240 batch (2026-08-18)** —

- **#240**: the login `Create one` link and its reciprocal register-page `Sign in` link now carry a persistent `underline` at rest instead of `hover:underline` only, so the link no longer depends on colour alone (1.4.1).
- **#236**: the authenticated header's notification and account controls now carry `aria-label` (`Notifications` / `Notifications, N unread` / `Account menu`), and their glyphs are marked `aria-hidden`/`focusable="false"` (4.1.2), matching the #286 convention.
- **#237**: re-investigated rather than restyled. The title/helper/label/placeholder colors already clear 4.5:1 at rest — `text-foreground` and `text-muted-foreground` against `bg-card` compute to roughly 15:1 and 5.6:1 respectively in this theme. The axe failures were an artifact of `expectWcagBaseline`'s animation-settle wait: the GitHub-import panel enters via `AnimatePresence mode="wait"`, and `document.getAnimations()` can be transiently empty in the gap between the outgoing panel's exit finishing and the incoming panel's enter starting, so the old wait resolved before the enter animation began and axe sampled the panel still at its initial (near-zero-opacity) state. `waitForAnimationsSettled` in `e2e/accessibility.spec.ts` now re-checks after a fixed delay to close that window; with the fix, all four `github-import-*` targets measure 0 violations and their allowances have been removed. No application color changed for #237.
- **#238** was already resolved by the #289 sidebar regrouping (above); this batch only re-confirmed it.

This clears the four Phase 0 follow-up issues #118 opened (#236, #237, #238, #240) at the automated-baseline level described in this report. Issue [#239](https://github.com/Second-Origin/PARTHA/issues/239) is completed and its non-visual architecture equivalent is implemented. The dated manual close-out above records the maintainer-confirmed human checks; "WCAG 2.2 AA baseline established" still means that this report has no outstanding known violation in the tested scope, not a claim of full WCAG 2.2 AA conformance.

No confirmed automated violation is left only in this report.

## Architecture graph non-visual equivalent

The visual graph has partial accessibility affordances: individual React Flow nodes are
keyboard-focusable and have names containing classification, layer, description, file count, and
relationship trust state. Selecting a node opens a named modal inspector with responsibilities,
files, dependencies, and dependents.

The semantic list/table equivalent is implemented and [#239](https://github.com/Second-Origin/PARTHA/issues/239)
is completed. The manual screen-reader experience is recorded as maintainer-confirmed in the
dated close-out above.

## Known limitations

- Historical manual-baseline rows above remain preserved as historical evidence; the dated
  close-out above records the maintainer-confirmed checks for this validation cycle.
- Automated coverage is Chromium-only, desktop-only, dark-theme-only, and 100% zoom.
- axe cannot determine overall WCAG conformance, usability, reading order, quality of accessible
  names, screen-reader announcements, or whether the graph's non-visual experience is efficient.
- Selected states prioritize the first-use login, persistent shell, populated repository list,
  empty GitHub import form, successful small graph, and open inspector. Loading/error states and
  other product routes are outside this Phase 0 baseline.
- The original audit was on 2026-07-29; the latest automated revalidation is recorded above.
  Follow-up fixes must update both their issue status and the exact known-finding expectations in
  the automated baseline.
