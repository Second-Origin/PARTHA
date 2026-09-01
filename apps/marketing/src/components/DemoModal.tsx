import { useEffect, useRef, useState } from 'react';
import {
  CATEGORY_LABELS,
  SAMPLE_CATEGORIES,
  SAMPLE_FINDINGS,
  SAMPLE_LANGUAGES,
  SAMPLE_METRICS,
  SAMPLE_REPO,
  SIMULATION_STEPS,
  type ReviewSeverity,
} from '@/data/sampleAnalysis';

type Phase = 'idle' | 'running' | 'done';

const SEVERITY_STYLE: Record<ReviewSeverity, string> = {
  critical: 'bg-destructive/10 text-destructive',
  high: 'bg-destructive/10 text-destructive',
  medium: 'bg-warning/10 text-warning',
  low: 'bg-primary/10 text-primary',
  info: 'bg-muted text-muted-foreground',
};

const CATEGORY_STATE_STYLE: Record<string, string> = {
  assessed: 'bg-success/10 text-success',
  partially_assessed: 'bg-warning/10 text-warning',
  not_assessed: 'bg-muted text-muted-foreground',
  insufficient_evidence: 'bg-muted text-muted-foreground',
};

/** Opened from the reused LandingPage's "Log in" nav hotspot and its "See
 * how it works" hero hotspot (#382 redesign) -- there is no login flow, no
 * dashboard, and no anchor-scrollable walkthrough in this standalone site,
 * so both hotspots lead here instead. A modal, not a page section: keeps
 * the reused landing artwork's own length and layout completely untouched,
 * the same interaction shape the real page already uses for its FAQ
 * answers. */
export function DemoModal({ onClose }: { onClose: () => void }) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [stepIndex, setStepIndex] = useState(0);
  const [tab, setTab] = useState<'review' | 'insights'>('review');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const run = () => {
    if (phase === 'running') return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setPhase('running');
    setStepIndex(0);
    SIMULATION_STEPS.forEach((_, index) => {
      timers.current.push(setTimeout(() => setStepIndex(index + 1), 550 * (index + 1)));
    });
    timers.current.push(setTimeout(() => setPhase('done'), 550 * SIMULATION_STEPS.length + 300));
  };

  const reset = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setPhase('idle');
    setStepIndex(0);
    setTab('review');
  };

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="demo-modal-title" className="fixed inset-0 z-50 grid place-items-center bg-foreground/30 p-5">
      <div className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-primary/35 bg-card shadow-2xl">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-5 border-b border-border bg-card p-6 sm:p-8 sm:pb-6">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-accent px-3 py-1 text-2xs font-semibold uppercase tracking-[0.14em] text-primary">
              Scripted simulation · sample repository
            </div>
            <h2 id="demo-modal-title" className="text-2xl font-semibold text-foreground">
              See what a PARTHA analysis produces
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
              A scripted walkthrough of a made-up sample repository ({SAMPLE_REPO.name}) -- not a live analysis of any
              real code. It uses PARTHA's actual finding categories and output shape.
            </p>
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

        <div className="p-6 sm:p-8">
          <div className="partha-surface overflow-hidden">
            <div className="flex items-center justify-between gap-4 border-b border-border bg-muted/50 px-5 py-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{SAMPLE_REPO.name}</p>
                <p className="text-2xs text-muted-foreground">
                  revision {SAMPLE_REPO.revision} · {SAMPLE_REPO.languages}
                </p>
              </div>
              {phase !== 'idle' && (
                <button
                  type="button"
                  onClick={reset}
                  className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-2xs font-semibold text-foreground hover:bg-accent"
                >
                  Reset
                </button>
              )}
            </div>

            {phase === 'idle' && (
              <div className="flex flex-col items-center gap-4 px-6 py-16 text-center">
                <p className="max-w-sm text-sm text-muted-foreground">
                  Run the simulation to watch PARTHA walk through a sample repository and produce Engineering Review
                  and Repository Insights output.
                </p>
                <button
                  type="button"
                  onClick={run}
                  className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_hsl(var(--primary)/0.2)] transition-colors hover:bg-primary/90"
                >
                  Run the simulation
                </button>
              </div>
            )}

            {phase !== 'idle' && (
              <div className="px-5 py-6">
                <ol className="space-y-2.5" aria-label="Simulation progress">
                  {SIMULATION_STEPS.map((step, index) => {
                    const complete = index < stepIndex;
                    const active = index === stepIndex && phase === 'running';
                    return (
                      <li key={step} className="flex items-center gap-3 text-sm">
                        <span
                          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-2xs font-bold ${
                            complete
                              ? 'bg-success text-success-foreground'
                              : active
                                ? 'animate-pulse bg-primary text-primary-foreground'
                                : 'bg-muted text-muted-foreground'
                          }`}
                        >
                          {complete ? '✓' : index + 1}
                        </span>
                        <span className={complete || active ? 'text-foreground' : 'text-muted-foreground'}>{step}</span>
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}

            {phase === 'done' && (
              <div className="animate-fade-in border-t border-border px-5 py-6">
                <div role="tablist" aria-label="Sample analysis results" className="mb-6 flex gap-1 border-b border-border">
                  {(['review', 'insights'] as const).map((value) => (
                    <button
                      key={value}
                      type="button"
                      role="tab"
                      aria-selected={tab === value}
                      onClick={() => setTab(value)}
                      className={`px-4 py-2.5 text-sm font-semibold capitalize transition-colors ${
                        tab === value ? 'border-b-2 border-primary text-foreground' : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {value === 'review' ? 'Engineering Review' : 'Repository Insights'}
                    </button>
                  ))}
                </div>

                {tab === 'review' && (
                  <div className="space-y-6">
                    <div className="flex flex-wrap gap-2">
                      {SAMPLE_CATEGORIES.map((category) => (
                        <span
                          key={category.id}
                          title={category.explanation}
                          className={`rounded-full px-3 py-1 text-2xs font-semibold ${CATEGORY_STATE_STYLE[category.state]}`}
                        >
                          {category.label}
                          {category.findingCount > 0 ? ` (${category.findingCount})` : ''}
                        </span>
                      ))}
                    </div>
                    <ul className="space-y-4">
                      {SAMPLE_FINDINGS.map((finding) => (
                        <li key={finding.id} className="rounded-xl border border-border p-4">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <p className="font-semibold text-foreground">{finding.title}</p>
                            <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-2xs font-bold uppercase ${SEVERITY_STYLE[finding.severity]}`}>
                              {finding.severity}
                            </span>
                          </div>
                          <p className="mt-1 text-2xs font-medium uppercase tracking-wide text-muted-foreground">
                            {CATEGORY_LABELS[finding.category]}
                          </p>
                          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{finding.explanation}</p>
                          <p className="mt-2 text-sm leading-relaxed text-foreground">
                            <span className="font-semibold">Remediation: </span>
                            {finding.remediationGuidance}
                          </p>
                          <p className="mt-3 font-mono text-2xs text-muted-foreground">
                            {finding.path}:{finding.startLine}
                            {finding.endLine !== finding.startLine ? `–${finding.endLine}` : ''}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {tab === 'insights' && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {SAMPLE_METRICS.map((metric) => (
                        <div key={metric.id} title={metric.definition} className="rounded-xl border border-border p-4">
                          <p className="text-2xl font-bold text-foreground">{metric.value}</p>
                          <p className="mt-1 text-2xs font-medium text-muted-foreground">{metric.label}</p>
                        </div>
                      ))}
                    </div>
                    <div>
                      <p className="mb-2 text-2xs font-semibold uppercase tracking-wide text-muted-foreground">Languages</p>
                      <div className="flex h-3 overflow-hidden rounded-full bg-muted">
                        {SAMPLE_LANGUAGES.map((language, index) => (
                          <div
                            key={language.key}
                            style={{ width: `${language.value}%` }}
                            className={index === 0 ? 'bg-primary' : index === 1 ? 'bg-primary/60' : 'bg-primary/30'}
                            title={`${language.label}: ${language.value}%`}
                          />
                        ))}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-muted-foreground">
                        {SAMPLE_LANGUAGES.map((language) => (
                          <span key={language.key}>
                            {language.label} {language.value}%
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
