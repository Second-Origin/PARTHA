import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import { Boxes, CheckCircle2, Info, Package, ShieldCheck, Sparkles } from 'lucide-react';
import type { Repository } from '@/shared/types';
import { RevisionManifestPanel } from '@/features/architecture/components/RevisionManifestPanel';
import { cn } from '@/shared/utils/cn';
import { useRepositoryOutcomeSummary, type OutcomeAssessmentState } from '../hooks/useRepositoryOutcomeSummary';

interface RepositoryOutcomeSummaryProps {
  repository: Repository;
}

/**
 * Leads the repository landing view with a concise, evidence-backed summary
 * (#176) instead of the snapshot/manifest identity that used to sit there.
 * Every value comes from useRepositoryOutcomeSummary, which reads only the
 * existing Architecture/Review/Dependencies/Insights APIs -- nothing here is
 * computed or generated client-side. Snapshot identity itself is still
 * reachable, one click away, via the same RevisionManifestPanel Architecture
 * already uses.
 */
export function RepositoryOutcomeSummary({ repository }: RepositoryOutcomeSummaryProps) {
  const summary = useRepositoryOutcomeSummary(repository);
  const [verifyOpen, setVerifyOpen] = useState(false);

  // No severity-based color-coding here: a diagnostic-category count is not a
  // graded quality judgment, and styling it like one misrepresents it (#335).
  // The one exception is the genuinely positive "no findings" result.
  const hasFindings = summary.headline.state === 'assessed' && summary.headline.categoryId !== null;
  const HeadlineIcon = hasFindings ? Info : CheckCircle2;

  const stackValue =
    summary.stack.state === 'assessed'
      ? [summary.stack.language, summary.stack.framework].filter(Boolean).join(' / ') || 'Not detected'
      : null;
  const structureValue =
    summary.structure.state === 'assessed' ? `${summary.structure.totalModules} modules` : null;
  const dependenciesValue =
    summary.dependencies.state === 'assessed' ? `${summary.dependencies.totalDependencies} tracked` : null;

  return (
    <section aria-label="Repository outcome summary" className="mb-6 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-foreground">What to know</h2>
          <p className="mt-1 text-xs text-muted-foreground">Evidence-backed facts from the sealed repository snapshot.</p>
        </div>
        <button
          type="button"
          onClick={() => setVerifyOpen((open) => !open)}
          aria-expanded={verifyOpen}
          aria-controls="repository-outcome-verify"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-accent/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          {verifyOpen ? 'Hide verification' : 'Verify'}
        </button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SummaryTile
          icon={Sparkles}
          label="Stack"
          state={summary.stack.state}
          value={stackValue}
          detail={summary.stack.state === 'assessed' ? summary.stack.architecturePattern : null}
        />
        <SummaryTile
          icon={Boxes}
          label="Structure"
          state={summary.structure.state}
          value={structureValue}
          detail={summary.structure.state === 'assessed' ? `${summary.structure.totalNodes} components` : null}
        />
        <SummaryTile icon={Package} label="Dependencies" state={summary.dependencies.state} value={dependenciesValue} />
      </div>

      <div
        className={cn(
          'mt-3 flex items-start gap-2 rounded-lg border p-3',
          hasFindings ? 'border-border bg-accent/40' : 'border-border bg-muted/30',
        )}
      >
        <HeadlineIcon className={cn('mt-0.5 h-4 w-4 shrink-0', hasFindings ? 'text-primary' : 'text-muted-foreground')} />
        <div className="min-w-0">
          <p className="text-2xs font-medium uppercase tracking-wide text-muted-foreground">Headline</p>
          <p className="text-sm text-foreground">
            {summary.headline.state === 'loading' ? (
              'Loading...'
            ) : summary.headline.state === 'assessed' ? (
              hasFindings ? (
                <Link to={`/review?category=${summary.headline.categoryId}`} className="underline decoration-dotted underline-offset-2 hover:text-primary">
                  {summary.headline.message}
                </Link>
              ) : (
                summary.headline.message
              )
            ) : (
              'Not assessed'
            )}
          </p>
        </div>
      </div>

      {summary.coverage.state === 'assessed' && (
        <p className="mt-3 text-2xs text-muted-foreground">
          Assessed via {summary.coverage.extractorCount} extractor{summary.coverage.extractorCount === 1 ? '' : 's'} across{' '}
          {summary.coverage.languageCount} detected language{summary.coverage.languageCount === 1 ? '' : 's'}.
        </p>
      )}

      {verifyOpen && (
        <div id="repository-outcome-verify" className="mt-4">
          <RevisionManifestPanel repositoryId={repository.id} />
        </div>
      )}
    </section>
  );
}

function SummaryTile({
  icon: Icon,
  label,
  state,
  value,
  detail,
}: {
  icon: LucideIcon;
  label: string;
  state: OutcomeAssessmentState;
  value: string | null;
  detail?: string | null;
}) {
  return (
    <div className="rounded-lg border border-border bg-background/50 p-3">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-2xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1.5 text-sm font-medium text-foreground">
        {state === 'loading' ? 'Loading...' : state === 'assessed' ? value : 'Not assessed'}
      </p>
      {state === 'assessed' && detail && <p className="text-xs text-muted-foreground">{detail}</p>}
    </div>
  );
}
