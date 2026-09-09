import {
  ArrowRight,
  BarChart3,
  Boxes,
  ClipboardCheck,
  ExternalLink,
  FileText,
  Network,
  Play,
  Plus,
  Sparkles,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { cn } from '@/utils/cn';
import type { useLandingTheme } from '@/hooks/useLandingTheme';
import { faqAnswers, faqQuestions } from '@/data/faq';
import { DISCORD_URL, FOOTER_COLUMNS } from '@/data/site';
import parthaLogo from '@/assets/partha-logo.svg';

/**
 * Phone / tablet layout for the landing page (< 1024px). There is no authored
 * mobile version of the 1728-wide design canvas, so this is a purpose-built
 * responsive layout -- but it borrows that canvas's visual language: a heavy
 * Title Case display face, an editorial serif italic for the hero sub-copy, a
 * script accent, an outline eyebrow pill, pill CTAs with icons, and the
 * alternating peach / teal-blue tinted story cards. Same content and the same
 * demo / run-it-yourself dialogs as desktop; the 3.3 MB design SVG never loads
 * here.
 */
interface MobileLandingProps {
  theme: ReturnType<typeof useLandingTheme>;
  onOpenDemo: () => void;
  onOpenRunItYourself: () => void;
}

const STORY_CARDS = [
  {
    tone: 'blue' as const,
    label: 'System view',
    title: ['See How The', 'System Fits', 'Together'],
    body: 'Modules, dependencies, routes, and relationships, mapped from one repository model rather than a parser per feature.',
  },
  {
    tone: 'peach' as const,
    label: 'Source evidence',
    title: ['Know Where Every', 'Finding Came From'],
    body: 'Every supported fact traces to the exact file, symbol, line span, and revision it was extracted from.',
  },
  {
    tone: 'blue' as const,
    label: 'Honest by default',
    title: ['Honest About', 'Its Limits'],
    body: 'The same revision always seals the same snapshot, and anything that could not be assessed stays visibly unassessed.',
  },
];

const STEPS = [
  { title: 'Add a repository', body: 'Upload a ZIP/TAR archive or import a public GitHub repository over HTTPS.' },
  { title: 'Run analysis', body: 'A durable background job seals an immutable snapshot for that exact revision.' },
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

function PrimaryButton({ children, onClick, href }: { children: ReactNode; onClick?: () => void; href?: string }) {
  const cls =
    'inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-3.5 text-sm font-semibold text-primary-foreground shadow-[0_12px_26px_hsl(var(--primary)/0.25)] transition-colors hover:bg-primary/90';
  return href ? (
    <a href={href} target="_blank" rel="noreferrer" className={cls}>
      {children}
    </a>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {children}
    </button>
  );
}

function SecondaryButton({ children, onClick, href }: { children: ReactNode; onClick?: () => void; href?: string }) {
  const cls =
    'inline-flex items-center justify-center gap-2 rounded-full border border-primary/45 bg-card px-6 py-3.5 text-sm font-semibold text-foreground transition-colors hover:bg-accent';
  return href ? (
    <a href={href} target="_blank" rel="noreferrer" className={cls}>
      {children}
    </a>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {children}
    </button>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-primary/40 px-3 py-1 text-2xs font-semibold uppercase tracking-[0.16em] text-primary">
      <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
      {children}
    </span>
  );
}

export function MobileLanding({ theme, onOpenDemo, onOpenRunItYourself }: MobileLandingProps) {
  // The wordmark in partha-logo.svg is near-black with no dark asset; knock it
  // to white on the dark canvas so it stays legible.
  const dark = theme.resolved === 'dark';

  return (
    <div className="mx-auto w-full max-w-3xl px-5 pb-16">
      <header className="sticky top-0 z-30 -mx-5 flex items-center justify-between border-b border-border/60 bg-background/85 px-5 py-3 backdrop-blur">
        <a href="#top" className="flex items-center">
          <img
            src={parthaLogo}
            alt="PARTHA"
            className={cn('h-6 w-auto', dark && 'brightness-0 invert')}
            draggable="false"
          />
        </a>
        <ThemeSwitcher preference={theme.preference} onChange={theme.setPreference} />
      </header>

      {/* Hero */}
      <section id="top" className="relative isolate pt-14 sm:pt-20">
        <div
          aria-hidden="true"
          className="absolute -left-24 -top-10 -z-10 h-64 w-64 rounded-full bg-primary/15 blur-3xl"
        />
        <Eyebrow>Repository intelligence system</Eyebrow>
        <h2 className="mt-4 font-sans text-[2.4rem] font-extrabold leading-[1.06] tracking-tight text-foreground sm:text-6xl">
          Reveal The System Behind The Code.
        </h2>
        <p className="mt-5 max-w-xl font-serif text-lg italic leading-relaxed text-muted-foreground sm:text-xl">
          PARTHA analyses a Git repository at a specific revision and produces a sealed, evidence-backed model of the
          system. Deterministic. Reproducible. Honest about its limits.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <SecondaryButton onClick={onOpenDemo}>
            <Play className="h-4 w-4 fill-primary text-primary" aria-hidden="true" /> See how it works
          </SecondaryButton>
          <PrimaryButton onClick={onOpenRunItYourself}>
            Analyze a repository <ExternalLink className="h-4 w-4" aria-hidden="true" />
          </PrimaryButton>
        </div>
        <p className="mt-5 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Connect a repository. PARTHA maps the system. You verify the evidence.
        </p>
      </section>

      {/* Meet Partha */}
      <section id="product" className="mt-20 scroll-mt-20 text-center">
        <p className="text-3xl font-extrabold text-foreground">
          Meet <span className="font-script text-[2.75rem] font-bold leading-none text-primary">Partha</span>
        </p>
        <p className="mt-1 font-script text-2xl text-muted-foreground">Understand your codebase</p>

        <div className="mt-8 space-y-4 text-left">
          {STORY_CARDS.map((card) => (
            <article
              key={card.label}
              className={cn(
                'rounded-3xl border p-6',
                card.tone === 'blue'
                  ? 'border-brand-blue/25 bg-brand-blue/10'
                  : 'border-primary/20 bg-accent',
              )}
            >
              <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{card.label}</p>
              <h3 className="mt-2 font-sans text-2xl font-extrabold leading-tight tracking-tight text-foreground">
                {card.title.map((line) => (
                  <span key={line} className="block">
                    {line}
                  </span>
                ))}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{card.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="mt-16 scroll-mt-20">
        <h3 className="font-sans text-3xl font-extrabold tracking-tight text-foreground">How It Works</h3>
        <ol className="mt-6 space-y-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-4 rounded-2xl border border-border bg-card p-5">
              <span
                className={cn(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-extrabold',
                  index === 1 ? 'bg-primary/10 text-primary' : 'bg-brand-blue/12 text-brand-blue',
                )}
              >
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

      {/* Capabilities */}
      <section id="capabilities" className="mt-16 scroll-mt-20">
        <h3 className="font-sans text-3xl font-extrabold tracking-tight text-foreground">Capabilities</h3>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {CAPABILITIES.map(({ icon: Icon, title, body }, index) => (
            <div key={title} className="rounded-2xl border border-border bg-card p-5">
              <span
                className={cn(
                  'inline-flex h-10 w-10 items-center justify-center rounded-xl',
                  index % 2 === 0 ? 'bg-primary/10 text-primary' : 'bg-brand-blue/12 text-brand-blue',
                )}
              >
                <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
              <p className="mt-3 font-semibold text-foreground">{title}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mt-16 scroll-mt-20">
        <h3 className="font-sans text-3xl font-extrabold tracking-tight text-foreground">
          Frequently Asked Questions
        </h3>
        <div className="mt-5 divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
          {faqQuestions.map((question, index) => (
            <details key={question} className="group px-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-sm font-semibold text-foreground [&::-webkit-details-marker]:hidden">
                {question}
                <Plus
                  className="h-4 w-4 shrink-0 text-primary transition-transform duration-200 group-open:rotate-45"
                  aria-hidden="true"
                />
              </summary>
              <p className="pb-4 text-sm leading-relaxed text-muted-foreground">{faqAnswers[index]}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mt-16 overflow-hidden rounded-[2rem] border border-primary/25 bg-accent p-7">
        <h3 className="font-sans text-2xl font-extrabold tracking-tight text-foreground">Run PARTHA On Your Own Code</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          It&apos;s open source and self-hosted — no waitlist, no hosted service. Fork it, run it locally, and point it
          at a repository you actually care about.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <PrimaryButton onClick={onOpenRunItYourself}>
            Get started <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </PrimaryButton>
          <SecondaryButton href={DISCORD_URL}>Join the Discord</SecondaryButton>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-16 border-t border-border/60 pt-10">
        <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-4">
          {FOOTER_COLUMNS.map((column) => (
            <div key={column.heading}>
              <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{column.heading}</p>
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
        <div className="mt-10 flex flex-col items-start gap-4 border-t border-border/60 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">© {new Date().getFullYear()} PARTHA · Apache-2.0</p>
          <ThemeSwitcher preference={theme.preference} onChange={theme.setPreference} />
        </div>
      </footer>
    </div>
  );
}
