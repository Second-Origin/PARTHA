import logo from '@/assets/partha-logo.svg';

const GITHUB_URL = 'https://github.com/Second-Origin/PARTHA';

export function Hero({ onJoinWaitlist }: { onJoinWaitlist: () => void }) {
  return (
    <header className="relative overflow-hidden">
      <div aria-hidden="true" className="absolute -left-24 -top-24 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
      <div aria-hidden="true" className="absolute -right-24 top-40 h-96 w-96 rounded-full bg-primary/5 blur-3xl" />

      <div className="relative mx-auto flex max-w-5xl items-center justify-between px-6 py-7 sm:px-8">
        <a href="/" className="block w-[120px]" aria-label="PARTHA home">
          <img src={logo} alt="PARTHA" className="h-auto w-full" />
        </a>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-foreground hover:bg-accent"
        >
          View on GitHub
        </a>
      </div>

      <div className="relative mx-auto max-w-3xl px-6 pb-20 pt-10 text-center sm:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">Repository intelligence</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Reveal the system behind the code.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          PARTHA turns a repository revision into one sealed, queryable model, then uses it to explain architecture,
          dependencies, review findings, and insights — without letting each feature invent its own interpretation.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <a
            href="#simulation"
            className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_hsl(var(--primary)/0.2)] transition-colors hover:bg-primary/90"
          >
            See a scripted walkthrough
          </a>
          <button
            type="button"
            onClick={onJoinWaitlist}
            className="rounded-xl border border-border px-5 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-accent"
          >
            Join the waitlist
          </button>
        </div>
        <p className="mt-6 text-2xs text-muted-foreground">
          PARTHA is not running as a hosted service right now. Everything below is either a scripted demo or
          something you can run yourself locally.
        </p>
      </div>
    </header>
  );
}
