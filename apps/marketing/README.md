# PARTHA marketing site

A free, static marketing site for PARTHA (#382). On desktop it reuses the real `apps/frontend` landing page — the
same 1728px-wide authored design, the same light/dark theme system, the same FAQ and footer — as its visual basis,
ported in rather than re-invented, with two behavioral differences since this site has no backend or accounts at
all:

- The "Log In" nav hotspot and the "See how it works" hero hotspot both open a scripted product simulation instead
  (`src/components/DemoModal.tsx`), using canned sample data — there's nothing live to log into or scroll to a
  walkthrough of, so both lead to the same demo.
- Every "Analyze a Repository" hotspot has no live backend to analyze against, so it opens fork/clone setup
  instructions instead (`src/components/RunItYourselfModal.tsx`), plus a note encouraging people to star the repo.

There is no waitlist or hosted-beta path anywhere on this site: PARTHA is self-hosted only for the foreseeable
future, with no hosted service planned, so there's nothing to wait for.

## Two layouts, one breakpoint

The authored desktop design is a single 1728px-wide SVG with invisible percentage-positioned tap targets on top.
That does not shrink into a usable phone page — it just becomes unreadable — so the site renders **one of two
layouts, never both**, split at 1024px by `useMediaQuery`:

- **≥ 1024px** — the authored canvas described above, unchanged.
- **< 1024px** — `MobileLanding.tsx`, a purpose-built responsive layout. It is not the desktop artwork reflowed: it
  is authored to the *PARTHA Foundations v1* brand handoff (Montserrat Alternates for display, Proza Libre for
  body, Cormorant Upright for one accent phrase; Deep Plum / Deep Blue / Burnt Orange / Signal Orange in their
  defined roles) and composes the designer's own illustration exports from `src/assets/landing/mobile-*.svg`.

Because only one layout is in the DOM at a time, the 3.3MB desktop SVG never loads on a phone. The mobile
illustrations total roughly 230KB gzipped and are `loading="lazy"`.

Deliberately independent of `apps/frontend` — no backend dependency, and nothing here talks to the real Render/Neon
deployment (which is paused, not live — see #375/#377). It builds and runs entirely on its own; shared visual assets
(SVG artwork, theme hook, tokens) are copied in directly rather than imported cross-package, to keep it that way.

## Local development

```bash
cd apps/marketing
npm install
npm run dev
```

Opens at `http://localhost:5173` (or the next free port Vite picks; the repo's `.claude/launch.json` runs it on
`5174` alongside the real frontend dev server on `5173`). The entire page works with zero configuration — there is
no backend call anywhere on the site.

## Verification

> **This package has no CI coverage.** No job in `.github/workflows/` builds, lints, or type-checks
> `apps/marketing`, and there are no tests here. Run these locally before merging anything that touches it, and
> check both layouts in a browser — a change that only breaks below 1024px will not be caught for you.

```bash
npm run typecheck  # tsc -b --noEmit
npm run lint       # eslint .
npm run build      # tsc -b && vite build -- outputs to dist/
npm run preview    # serve the production build locally
```

## Deploying on Vercel

This project is intentionally **not** part of the root npm workspace (`apps/frontend` is) — it has its own
`package.json`/`node_modules`, so Vercel can build it in complete isolation from the rest of the monorepo.

1. In the Vercel dashboard: **Add New → Project**, import the `Second-Origin/PARTHA` GitHub repository.
2. Set the project's **Root Directory** to `apps/marketing`. Vercel auto-detects the Vite framework preset from
   there; `vercel.json` in this directory pins the build command and output directory explicitly regardless.
3. No env vars needed to deploy — the page renders and the simulation works with zero configuration.
4. Deploy. Vercel gives you a `*.vercel.app` URL immediately; a custom domain can be attached afterward under
   **Settings → Domains**.

## Structure

- `src/App.tsx` — chooses the layout for the current viewport. At ≥1024px it renders the authored SVG artwork
  (`src/assets/landing/`) with the invisible nav/hero/footer hotspots overlaid; below that it renders
  `MobileLanding`. Both wire the same two behavioral differences described above.
- `src/components/MobileLanding.tsx` — the responsive phone/tablet layout: sticky header, hero, "Meet Partha",
  three story cards, how-it-works steps, capability list, a native `<details>` FAQ accordion, CTA band, and footer.
- `src/hooks/useMediaQuery.ts` — the 1024px breakpoint gate (`useSyncExternalStore` over `matchMedia`).
- `src/components/DemoModal.tsx`, `RunItYourselfModal.tsx` — the two interactive surfaces reached from the
  hotspots, both built on `src/components/Modal.tsx` (a centered, focus-trapped, Escape-dismissable dialog).
- `src/hooks/useLandingTheme.ts`, `src/components/ThemeSwitcher.tsx` — verbatim ports of the real frontend's
  light/dark/system theme store and toggle.
- `src/data/site.ts`, `src/data/faq.ts` — footer columns, external URLs, and FAQ copy shared by both layouts, so
  the desktop overlay's positioned footer links and the mobile footer cannot drift apart.
- `src/data/sampleAnalysis.ts` — the canned data behind the demo simulation, using PARTHA's real finding
  categories/severities/output shape.

## What this deliberately does not do

- Does not call the real PARTHA API — the "simulation" is entirely canned data in `src/data/sampleAnalysis.ts`,
  clearly labeled in the UI as a scripted sample-repository walkthrough, not a live analysis.
- Does not create or need a PARTHA account, login, or session — the reused landing page's "Log In" hotspot opens the
  demo instead of a login flow.
- Does not offer a waitlist or any hosted-beta path — the product is self-hosted only, with no hosted service
  planned, so "run it yourself" is the only call to action.
- Does not touch `apps/frontend`, the backend, or `render.yaml` — those stay exactly as they are, paused.
