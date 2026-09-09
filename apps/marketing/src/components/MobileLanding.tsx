import type { ReactNode } from 'react';
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
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { cn } from '@/utils/cn';
import type { useLandingTheme } from '@/hooks/useLandingTheme';
import { faqAnswers, faqQuestions } from '@/data/faq';
import { DISCORD_URL, FOOTER_COLUMNS } from '@/data/site';
import parthaLogo from '@/assets/partha-logo.svg';

/**
 * Phone / tablet layout for the landing page (< 1024px). The authored 1728-wide
 * design canvas only shrinks on a narrow screen, so below `lg` App.tsx renders
 * this instead. It follows PARTHA Foundations v1: Montserrat Alternates
 * (`font-display`) for headings and buttons, Proza Libre (`font-sans`) for all
 * reading text, Cormorant Upright (`font-accent`) for one expressive phrase,
 * and the four brand colours in their assigned roles -- Signal Orange for the
 * CTA and focus moments only, Deep Blue for architecture / technical, Deep Plum
 * for headlines and body, on ~70% neutral surface. Same content and dialogs as
 * desktop; the 3.3 MB design SVG never loads here.
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
    title: 'See how the system fits together',
    body: 'Modules, dependencies, routes, and relationships, mapped from one repository model rather than a parser per feature.',
  },
  {
    tone: 'orange' as const,
    label: 'Source evidence',
    title: 'Know where every finding came from',
    body: 'Every supported fact traces to the exact file, symbol, line span, and revision it was extracted from.',
  },
  {
    tone: 'neutral' as const,
    label: 'Honest by default',
    title: 'Honest about its limits',
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

const BTN_BASE =
  'inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 font-display text-sm font-semibold transition-colors';

function PrimaryButton({ children, onClick, href }: { children: ReactNode; onClick?: () => void; href?: string }) {
  const cls = cn(
    BTN_BASE,
    'bg-primary text-primary-foreground shadow-[0_12px_26px_hsl(var(--primary)/0.24)] hover:bg-primary/90',
  );
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
  const cls = cn(BTN_BASE, 'border border-foreground/25 bg-card text-foreground hover:bg-accent');
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

function SectionHeading({ children, id }: { children: ReactNode; id: string }) {
  return (
    <h3
      id={id}
      className="scroll-mt-24 font-display text-[1.75rem] font-semibold leading-[1.15] tracking-tight text-foreground"
    >
      {children}
    </h3>
  );
}

export function MobileLanding({ theme, onOpenDemo, onOpenRunItYourself }: MobileLandingProps) {
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
        <div aria-hidden="true" className="absolute -left-24 -top-8 -z-10 h-56 w-56 rounded-full bg-primary/10 blur-3xl" />
        <span className="inline-flex items-center gap-2 rounded-full border border-foreground/15 px-3 py-1 font-sans text-2xs font-medium uppercase tracking-[0.16em] text-burnt-orange">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
          Repository intelligence system
        </span>
        <h2 className="mt-5 font-display text-[2.5rem] font-bold leading-[1.08] tracking-tight text-foreground sm:text-[3.25rem]">
          Reveal the system behind the code.
        </h2>
        <p className="mt-5 max-w-xl font-sans text-lg leading-[1.6] text-muted-foreground">
          PARTHA analyses a Git repository at a specific revision and produces a sealed, evidence-backed model of the
          system. Deterministic. Reproducible. Honest about its limits.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <PrimaryButton onClick={onOpenRunItYourself}>
            Analyze a repository <ExternalLink className="h-4 w-4" aria-hidden="true" />
          </PrimaryButton>
          <SecondaryButton onClick={onOpenDemo}>
            <Play className="h-3.5 w-3.5 fill-current" aria-hidden="true" /> See how it works
          </SecondaryButton>
        </div>
        <p className="mt-6 font-sans text-2xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          Connect a repository. PARTHA maps the system. You verify the evidence.
        </p>
      </section>

      {/* Meet Partha + product story */}
      <section id="product" className="mt-20 scroll-mt-24">
        <p className="text-center font-display text-2xl font-semibold text-foreground">
          Meet <span className="font-accent text-[2.6rem] font-medium italic leading-none text-primary">Partha</span>
        </p>

        <div className="mt-8 space-y-4">
          {STORY_CARDS.map((card) => (
            <article
              key={card.label}
              className={cn(
                'rounded-3xl border p-6',
                card.tone === 'blue' && 'border-secondary/25 bg-secondary/[0.08]',
                card.tone === 'orange' && 'border-primary/20 bg-accent',
                card.tone === 'neutral' && 'border-border bg-card',
              )}
            >
              <p
                className={cn(
                  'font-sans text-2xs font-semibold uppercase tracking-[0.16em]',
                  card.tone === 'orange' ? 'text-burnt-orange' : 'text-secondary',
                )}
              >
                {card.label}
              </p>
              <h4 className="mt-2 font-display text-xl font-semibold leading-snug text-foreground">{card.title}</h4>
              <p className="mt-2 font-sans text-sm leading-[1.55] text-muted-foreground">{card.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mt-16">
        <SectionHeading id="how-it-works">How it works</SectionHeading>
        <ol className="mt-6 space-y-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-4 rounded-2xl border border-border bg-card p-5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary/12 font-display text-sm font-bold text-secondary">
                {index + 1}
              </span>
              <div>
                <p className="font-display text-base font-semibold text-foreground">{step.title}</p>
                <p className="mt-1 font-sans text-sm leading-[1.55] text-muted-foreground">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* Capabilities */}
      <section className="mt-16">
        <SectionHeading id="capabilities">Capabilities</SectionHeading>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {CAPABILITIES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-2xl border border-border bg-card p-5">
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-secondary/10 text-secondary">
                <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
              <p className="mt-3 font-display text-base font-semibold text-foreground">{title}</p>
              <p className="mt-1 font-sans text-sm leading-[1.55] text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="mt-16">
        <SectionHeading id="faq">Frequently asked questions</SectionHeading>
        <div className="mt-5 divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
          {faqQuestions.map((question, index) => (
            <details key={question} className="group px-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-display text-sm font-semibold text-foreground [&::-webkit-details-marker]:hidden">
                {question}
                <Plus
                  className="h-4 w-4 shrink-0 text-primary transition-transform duration-200 group-open:rotate-45"
                  aria-hidden="true"
                />
              </summary>
              <p className="pb-4 font-sans text-sm leading-[1.55] text-muted-foreground">{faqAnswers[index]}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mt-16 rounded-[2rem] border border-primary/20 bg-accent p-7">
        <h3 className="font-display text-2xl font-semibold tracking-tight text-foreground">Run PARTHA on your own code</h3>
        <p className="mt-2 font-sans text-sm leading-[1.6] text-muted-foreground">
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
              <p className="font-sans text-2xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {column.heading}
              </p>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      target={link.external ? '_blank' : undefined}
                      rel={link.external ? 'noreferrer' : undefined}
                      className="font-sans text-sm text-foreground transition-colors hover:text-primary"
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
          <p className="font-sans text-xs text-muted-foreground">© {new Date().getFullYear()} PARTHA · Apache-2.0</p>
          <ThemeSwitcher preference={theme.preference} onChange={theme.setPreference} />
        </div>
      </footer>
    </div>
  );
}
