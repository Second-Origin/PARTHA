# PARTHA marketing site

A free, static marketing site for PARTHA (#382): a scripted product simulation using canned sample data, a "run it
yourself" call to action pointing at the main repository, and a waitlist form. Deliberately independent of
`apps/frontend` — no backend dependency, and nothing here talks to the real Render/Neon deployment (which is paused,
not live — see #375/#377). It builds and runs entirely on its own.

## Local development

```bash
cd apps/marketing
npm install
npm run dev
```

Opens at `http://localhost:5173` (or the next free port Vite picks). The waitlist form will show a "not configured"
error locally unless you also run `vercel dev` with the env vars below set — that's expected; the rest of the page
works fully without it.

## Verification

```bash
npm run typecheck  # tsc -b --noEmit
npm run lint       # eslint .
npm run test       # node --test against api/waitlist.ts, with fetch mocked -- no real network/GitHub call
npm run build      # tsc -b && vite build -- outputs to dist/
npm run preview    # serve the production build locally
```

## Deploying on Vercel

This project is intentionally **not** part of the root npm workspace (`apps/frontend` is) — it has its own
`package.json`/`node_modules`, so Vercel can build it in complete isolation from the rest of the monorepo.

1. In the Vercel dashboard: **Add New → Project**, import the `Second-Origin/PARTHA` GitHub repository.
2. Set the project's **Root Directory** to `apps/marketing`. Vercel auto-detects the Vite framework preset from
   there; `vercel.json` in this directory pins the build command and output directory explicitly regardless.
3. No required env vars to deploy the site itself — the page renders and the simulation works with zero
   configuration. The waitlist form needs two, added under **Settings → Environment Variables**, before it will
   actually store submissions (see below).
4. Deploy. Vercel gives you a `*.vercel.app` URL immediately; a custom domain can be attached afterward under
   **Settings → Domains**.

## Waitlist form setup (one-time)

There's no live Postgres to write submissions to (the real backend is paused). Instead, `api/waitlist.ts` — a Vercel
serverless function, deployed automatically alongside the site — appends each submission to a private GitHub Gist.
This needs no new third-party service: just a GitHub token, since the project already has a GitHub account.

1. Create an empty **secret** Gist at <https://gist.github.com>, with exactly one file named `waitlist.json`
   containing `[]`. Copy its id from the URL (the part after the last `/`).
2. Create a **fine-grained** GitHub Personal Access Token at
   <https://github.com/settings/personal-access-tokens/new>, scoped to **only** that Gist (Permissions → Gists →
   Read and write). Do not use a classic token with broader `repo` scope than this needs.
3. In the Vercel project, **Settings → Environment Variables**, add:
   - `WAITLIST_GITHUB_TOKEN` — the token from step 2.
   - `WAITLIST_GIST_ID` — the Gist id from step 1.
4. Redeploy (Vercel → Deployments → ⋯ → Redeploy) so the function picks up the new env vars.

Until both are set, the form fails with a clear "not configured yet" message instead of silently dropping
submissions or crashing — the rest of the site is unaffected either way.

To read submissions later: open the Gist directly, or `curl -H "Authorization: Bearer <token>"
https://api.github.com/gists/<gist-id>`.

## What this deliberately does not do

- Does not call the real PARTHA API — the "simulation" is entirely canned data in `src/data/sampleAnalysis.ts`,
  clearly labeled in the UI as a scripted sample-repository walkthrough, not a live analysis.
- Does not create or need a PARTHA account, login, or session.
- Does not touch `apps/frontend`, the backend, or `render.yaml` — those stay exactly as they are, paused.
