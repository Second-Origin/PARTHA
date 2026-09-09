import { ArrowRight, BarChart3, Boxes, ClipboardCheck, FileText, Network, Sparkles } from 'lucide-react';
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { cn } from '@/utils/cn';
import type { useLandingTheme } from '@/hooks/useLandingTheme';
import { faqAnswers, faqQuestions } from '@/data/faq';
import { DISCORD_URL, FOOTER_COLUMNS } from '@/data/site';
import parthaLogo from '@/assets/partha-logo.svg';

/**
 * The phone / tablet layout for the landing page (< 1024px). The authored
 * design canvas in App.tsx is a fixed 1728-wide composition -- on a narrow
 * screen it only shrinks, so its text becomes unreadable. Below `lg`, App.tsx
 * renders this instead: the same content and the same demo / run-it-yourself
 * dialogs, as a real responsive layout. The 3.3 MB design SVG is never loaded
 * here.
 */
interface MobileLandingProps {
  theme: ReturnType<typeof useLandingTheme>;
  onOpenDemo: () => void;
  onOpenRunItYourself: () => void;
}

const STEPS = [
  {
    title: 'Add a repository',
    body: 'Upload a ZIP/TAR archive or import a public GitHub repository over HTTPS.',
  },
  {
    title: 'Run analysis',
    body: 'A durable background job seals an immutable snapshot for that exact revision.',
  },
  {
    title: 'Inspect it from every angle',
    body: 'Architecture, Dependencies, Engineering Review, Insights, and Documentation all read that one shared model.',
  },
];

const CAPABILITIES = [
  { icon: Network, title: 'Architecture', body: 'A snapshot-backed module and relationship graph. Heuristic layers are labelled as heuristic.' },
  { icon: Boxes, title: 'Dependency Graph', body: 'Direct declarations from three manifest formats and pins from two lockfiles, on one identity.' },
  { icon: ClipboardCheck, title: 'Engineering Review', body: 'Evidence-addressed findings only. No overall score, grade, or health percentage.' },
  { icon: BarChart3, title: 'Repository Insights', body: 'Defined counts, ratios, diagnostics, and extraction coverage from one sealed snapshot.' },
  { icon: FileText, title: 'Documentation & exports', body: 'Structural docs plus JSON, Markdown, HTML, and PDF exports from the shared model.' },
  { icon: Sparkles, title: 'Optional AI', body: 'A provider you configure receives structural facts only — never source bytes or line spans.' },
];

export function MobileLanding({ theme, onOpenDemo, onOpenRunItYourself }: MobileLandingProps) {
  // The wordmark in partha-logo.svg is near-black and there is no dark asset;
  // knock the whole mark to white on the dark canvas so it stays legible.
  const dark = theme.resolved === 'dark';
  return (
    <div className="mx-auto w-full max-w-3xl px-5 pb-16">
      <header className="sticky top-0 z-30 -mx-5 flex items-center justify-between border-b border-border/70 bg-background/85 px-5 py-3 backdrop-blur">
        <a href="#top" className="flex items-center gap-2">
          <img
            src={parthaLogo}
            alt="PARTHA"
            className={cn('h-6 w-auto', dark && 'brightness-0 invert')}
            draggable="false"
          />
        </a>
        <ThemeSwitcher preference={theme.preference} onChange={theme.setPreference} />
      </header>

      <section id="top" className="pt-12 sm:pt-16">
        <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-primary">Repository intelligence system</p>
        <h2 className="mt-3 text-[2rem] font-semibold leading-tight text-foreground sm:text-5xl">
          Reveal the system behind the code.
        </h2>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
          PARTHA turns a repository revision into one sealed, queryable model, then explains architecture,
          dependencies, review findings, and more — without each feature inventing its own interpretation.
        </p>
        <div className="mt-7 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onOpenDemo}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-[0_10px_22px_hsl(var(--primary)/0.22)] transition-colors hover:bg-primary/90"
          >
            See how it works
          </button>
          <button
            type="button"
            onClick={onOpenRunItYourself}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-primary/40 px-5 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-accent"
          >
            Analyze a repository <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          Connect a repository. PARTHA maps the system. You verify the evidence.
        </p>
      </section>

      <section id="product" className="mt-16 scroll-mt-20 border-t border-border/70 pt-10">
        <h3 className="text-lg font-semibold text-foreground">One repository model, many consumers</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          A bounded extraction pipeline turns the selected revision into a persistent <code className="rounded bg-foreground/[0.06] px-1 py-0.5 text-[0.8em]">ri.v1</code>{' '}
          snapshot. Every product surface reads that shared, revision-bound, evidence-carrying model — and reports an
          unavailable state rather than falling back to a private interpretation.
        </p>
      </section>

      <section id="how-it-works" className="mt-14 scroll-mt-20">
        <h3 className="text-lg font-semibold text-foreground">How it works</h3>
        <ol className="mt-5 space-y-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-4 rounded-2xl border border-border p-4">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                {index + 1}
              </span>
              <div>
                <p className="font-semibold text-foreground">{step.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section id="capabilities" className="mt-14 scroll-mt-20">
        <h3 className="text-lg font-semibold text-foreground">Capabilities</h3>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {CAPABILITIES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-2xl border border-border p-4">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-primary">
                <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
              <p className="mt-3 font-semibold text-foreground">{title}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="faq" className="mt-14 scroll-mt-20">
        <h3 className="text-lg font-semibold text-foreground">Frequently asked questions</h3>
        <div className="mt-4 divide-y divide-border rounded-2xl border border-border">
          {faqQuestions.map((question, index) => (
            <details key={question} className="group px-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-sm font-semibold text-foreground [&::-webkit-details-marker]:hidden">
                {question}
                <ArrowRight
                  className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90"
                  aria-hidden="true"
                />
              </summary>
              <p className="pb-4 text-sm leading-relaxed text-muted-foreground">{faqAnswers[index]}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="mt-14 rounded-3xl border border-primary/25 bg-accent/60 p-6">
        <h3 className="text-lg font-semibold text-foreground">Run PARTHA on your own code</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          It&apos;s open source and self-hosted — no waitlist, no hosted service. Fork it, run it locally, and point it
          at a repository you actually care about.
        </p>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onOpenRunItYourself}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Get started
          </button>
          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-primary/40 px-5 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-accent"
          >
            Join the Discord
          </a>
        </div>
      </section>

      <footer className="mt-16 border-t border-border/70 pt-10">
        <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-4">
          {FOOTER_COLUMNS.map((column) => (
            <div key={column.heading}>
              <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">{column.heading}</p>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      target={link.external ? '_blank' : undefined}
                      rel={link.external ? 'noreferrer' : undefined}
                      className="text-sm text-foreground transition-colors hover:text-primary"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col items-start gap-4 border-t border-border/70 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">© {new Date().getFullYear()} PARTHA · Apache-2.0</p>
          <ThemeSwitcher preference={theme.preference} onChange={theme.setPreference} />
        </div>
      </footer>
    </div>
  );
}
