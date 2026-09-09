# PARTHA marketing site

A free, static marketing site for PARTHA (#382). It reuses the real `apps/frontend` landing page — the same
1728px-wide authored design, the same light/dark theme system, the same FAQ and footer — as its visual basis, ported
in rather than re-invented, with two behavioral differences since this site has no backend or accounts at all:

- The "Log In" nav hotspot and the "See how it works" hero hotspot both open a scripted product simulation instead
  (`src/components/DemoModal.tsx`), using canned sample data — there's nothing live to log into or scroll to a
  walkthrough of, so both lead to the same demo.
- Every "Analyze a Repository" hotspot has no live backend to analyze against, so it opens fork/clone setup
  instructions instead (`src/components/RunItYourselfModal.tsx`), plus a note encouraging people to star the repo.

There is no waitlist or hosted-beta path anywhere on this site: PARTHA is self-hosted only for the foreseeable
future, with no hosted service planned, so there's nothing to wait for.

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

- `src/App.tsx` — the ported landing page: renders the authored SVG artwork (`src/assets/landing/`), overlays the
  invisible nav/hero/footer hotspots on top, and wires the two behavioral differences described above.
- `src/components/DemoModal.tsx`, `RunItYourselfModal.tsx` — the two interactive surfaces reached from those
  hotspots.
- `src/hooks/useLandingTheme.ts`, `src/components/ThemeSwitcher.tsx` — verbatim ports of the real frontend's
  light/dark/system theme store and toggle.
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
