const GITHUB_URL = 'https://github.com/Second-Origin/PARTHA';

// Mirrors the exact commands in the repository's own README ("Run PARTHA
// locally") -- kept as a copy here (not a fetch of that file) since this
// site has no build-time dependency on the main repo at all, but checked
// against it directly rather than invented.
const BACKEND_COMMANDS = `git clone ${GITHUB_URL}.git
cd PARTHA/apps/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
cd ../..
npm run dev:backend`;

const FRONTEND_COMMANDS = `# in a second terminal
cd PARTHA
npm ci --prefix apps/frontend
npm run dev:frontend`;

export function RunItYourself() {
  return (
    <section id="run-it-yourself" className="mx-auto max-w-5xl px-6 py-20 sm:px-8">
      <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Run the real thing yourself</h2>
      <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">
        PARTHA is open source and runs locally with no external service beyond a public GitHub repository to analyze.
        No account, no waitlist, no hosted deployment required.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="partha-surface p-5">
          <p className="text-sm font-semibold text-foreground">1. Start the backend</p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-foreground/[0.04] p-4 text-2xs leading-relaxed text-foreground">
            <code>{BACKEND_COMMANDS}</code>
          </pre>
        </div>
        <div className="partha-surface p-5">
          <p className="text-sm font-semibold text-foreground">2. Start the frontend</p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-foreground/[0.04] p-4 text-2xs leading-relaxed text-foreground">
            <code>{FRONTEND_COMMANDS}</code>
          </pre>
          <p className="mt-3 text-2xs text-muted-foreground">
            Open <code className="rounded bg-foreground/[0.06] px-1 py-0.5">localhost:5173</code>, register a local
            account, add a repository, and start analysis.
          </p>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_hsl(var(--primary)/0.2)] transition-colors hover:bg-primary/90"
        >
          Fork the repository
        </a>
        <a
          href={`${GITHUB_URL}#run-partha-locally`}
          target="_blank"
          rel="noreferrer"
          className="rounded-xl border border-border px-5 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-accent"
        >
          Full setup guide
        </a>
      </div>
    </section>
  );
}
