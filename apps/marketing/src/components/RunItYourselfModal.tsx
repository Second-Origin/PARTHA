const GITHUB_URL = 'https://github.com/Second-Origin/PARTHA';

// Mirrors the exact commands in the repository's own README ("Run PARTHA
// locally") -- kept as a copy here (not a fetch of that file), but checked
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

/** Opened from the reused LandingPage's "Analyze a Repository" hotspots
 * (#382 redesign) -- there is no live backend for this button to actually
 * analyze anything against, so instead of running the scripted demo (see
 * DemoModal, reached from "Log in" instead) it shows how to run the real
 * product against a visitor's own code. No waitlist/hosted-beta path: the
 * product direction is self-host-only for the foreseeable future, so
 * "run it yourself" is the only call to action here. */
export function RunItYourselfModal({ onClose }: { onClose: () => void }) {
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="run-it-yourself-title" className="fixed inset-0 z-50 grid place-items-center bg-foreground/30 p-5">
      <div className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-3xl border border-primary/35 bg-card p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">Run it yourself</p>
            <h2 id="run-it-yourself-title" className="mt-2 text-xl font-semibold text-foreground">
              Analyze your own repository
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-xl border border-primary/30 px-3 py-2 text-sm font-semibold text-foreground hover:bg-accent"
          >
            Close
          </button>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          PARTHA isn&apos;t running as a hosted service, and there are no plans to host it -- it's open source and
          self-hosted only. It runs locally with no external service beyond a public GitHub repository to analyze --
          fork or clone it, run it, and try it on your own code.
        </p>

        <div className="mt-6 space-y-4">
          <div className="rounded-xl border border-border p-4">
            <p className="text-sm font-semibold text-foreground">1. Start the backend</p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-foreground/[0.04] p-4 text-2xs leading-relaxed text-foreground">
              <code>{BACKEND_COMMANDS}</code>
            </pre>
          </div>
          <div className="rounded-xl border border-border p-4">
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

        <div className="mt-6 border-t border-border pt-5 text-sm text-muted-foreground">
          <p>
            Finding this useful?{' '}
            <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="font-semibold text-primary underline underline-offset-2">
              Star the repo
            </a>{' '}
            to support the project and help others find it.
          </p>
        </div>
      </div>
    </div>
  );
}
