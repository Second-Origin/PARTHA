import { useEffect, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { AlertTriangle, CheckCircle2, ExternalLink, Info, ShieldCheck } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { useReviewStore } from '@/features/review/store';
import { useReview } from '@/features/review/hooks/useReview';
import { FindingCard } from '@/features/review/components/FindingCard';
import { FindingDetail } from '@/features/review/components/FindingDetail';
import { ReviewFilters } from '@/features/review/components/ReviewFilters';
import { ExportMenu } from '@/shared/components/ui/ExportMenu';
import { RevisionManifestPanel } from '@/features/architecture/components/RevisionManifestPanel';
import type { ReviewAssessmentState, ReviewSeverity } from '@/shared/types/review';

const STATE_LABEL: Record<ReviewAssessmentState, string> = {
  assessed: 'Assessed',
  partially_assessed: 'Partially assessed',
  not_assessed: 'Not assessed',
  insufficient_evidence: 'Insufficient evidence',
};

const SEVERITY_ORDER: ReviewSeverity[] = ['critical', 'high', 'medium', 'low', 'info'];

export function EngineeringReviewPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const reviewState = useReview();
  const {
    review,
    selectedFindingId,
    setSelectedFindingId,
    filteredFindings,
    setFilterDiagnosticCode,
  } = useReviewStore();

  useEffect(() => {
    setFilterDiagnosticCode(searchParams.get('diagnosticCode'));
  }, [searchParams, setFilterDiagnosticCode]);

  const findings = filteredFindings();
  const selectedFinding = useMemo(
    () => review?.findings.find((finding) => finding.id === selectedFindingId) ?? null,
    [review, selectedFindingId],
  );

  if (reviewState.emptyReason === 'no-completed-repositories') {
    return (
      <div>
        <PageHeader title="Engineering Review" description="Verified engineering concerns and their source evidence" />
        <EmptyState
          icon={ShieldCheck}
          title="No engineering review available"
          description="Upload and analyse a repository to assess its sealed snapshot."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }
  if (reviewState.emptyReason === 'no-active-repository') {
    return (
      <div>
        <PageHeader title="Engineering Review" description="Verified engineering concerns and their source evidence" />
        <EmptyState
          icon={ShieldCheck}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to inspect its exact revision."
        />
      </div>
    );
  }
  if (reviewState.loading) {
    return <StatusPanel text="Loading evidence-backed engineering review..." />;
  }
  // A repository can be analysed yet still have no sealed ri.v1 snapshot
  // (#178, same 404 contract as Dependencies/Architecture). That must read as
  // "run analysis again", never as a generic, unguided error message.
  if (reviewState.noSnapshot) {
    return (
      <div>
        <PageHeader title="Engineering Review" description="Verified engineering concerns and their source evidence" />
        <EmptyState
          icon={ShieldCheck}
          title="No sealed snapshot yet"
          description="This repository has no sealed Repository Intelligence snapshot for its current revision. Analyse it again to generate one."
          action={{ label: 'Run analysis', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }
  if (reviewState.error) {
    return <ErrorPanel message={reviewState.error} retry={reviewState.retry} />;
  }
  if (!review) return null;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Engineering Review"
        description={`${review.repositoryName} · ${review.revisionKind} ${review.revisionValue}`}
      >
        <Link
          to="/architecture"
          className="inline-flex items-center gap-1 rounded-xl border border-[#fa4d01]/30 px-3 py-2 text-xs font-semibold hover:bg-[#fff1e9]"
        >
          Architecture <ExternalLink className="h-3 w-3" />
        </Link>
        <Link
          to="/insights"
          className="inline-flex items-center gap-1 rounded-xl border border-[#fa4d01]/30 px-3 py-2 text-xs font-semibold hover:bg-[#fff1e9]"
        >
          Insights <ExternalLink className="h-3 w-3" />
        </Link>
        <ExportMenu repositoryId={review.repositoryId} target="review" />
      </PageHeader>

      <div className="mb-5 rounded-2xl border border-primary/30 bg-primary/5 p-4 text-sm text-foreground">
        PARTHA reports only findings supported by the selected sealed snapshot. Vulnerability scanning and
        categories without sufficient evidence are marked Not assessed.
      </div>

      <div className="mb-6">
        <RevisionManifestPanel repositoryId={review.repositoryId} />
      </div>

      <section className="mb-6 rounded-3xl border border-[#fa4d01]/20 bg-card p-6 shadow-[0_14px_34px_rgba(48,21,47,0.04)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-primary">Engineering review</p><h2 className="mt-1 text-lg font-semibold text-foreground">Evidence-backed summary</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{review.summary.message}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              No overall score, grade, health percentage, or category score is produced.
            </p>
          </div>
          <div className="grid w-full grid-cols-2 gap-2 sm:grid-cols-5 lg:w-auto">
            {SEVERITY_ORDER.map((severity) => (
              <div key={severity} className="rounded-xl bg-[#fff1e9] px-2 py-2 text-center">
                <p className="text-base font-semibold text-foreground">
                  {review.summary.findingsBySeverity[severity]}
                </p>
                <p className="text-[9px] uppercase text-muted-foreground">{severity}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mb-7">
        <h2 className="mb-3 text-sm font-medium text-foreground">Assessment matrix</h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {review.categories.map((category) => (
            <article key={category.id} className="rounded-2xl border border-[#fa4d01]/20 bg-card p-4 shadow-[0_10px_24px_rgba(48,21,47,0.03)]">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-medium text-foreground">{category.label}</h3>
                <span className="shrink-0 rounded-lg bg-[#fff1e9] px-2 py-1 text-[10px] text-muted-foreground">
                  {STATE_LABEL[category.state]}
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{category.explanation}</p>
              <p className="mt-2 text-[10px] text-muted-foreground">{category.findingCount} supported findings</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium text-foreground">Findings</h2>
            <p className="text-xs text-muted-foreground">{findings.length} matching supported findings</p>
          </div>
          <ReviewFilters />
        </div>
        {review.findings.length === 0 ? (
          <div className="rounded-3xl border border-[#fa4d01]/20 bg-card p-8 text-center">
            <CheckCircle2 className="mx-auto mb-2 h-7 w-7 text-emerald-400" />
            <h3 className="text-sm font-medium text-foreground">No evidence-backed findings</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              This does not mean every engineering category was assessed; consult the matrix above.
            </p>
          </div>
        ) : findings.length === 0 ? (
          <div className="rounded-3xl border border-[#fa4d01]/20 bg-card p-8 text-center">
            <Info className="mx-auto mb-2 h-7 w-7 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No findings match the selected filters.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {findings.map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                isSelected={finding.id === selectedFindingId}
                onClick={() => setSelectedFindingId(finding.id)}
              />
            ))}
          </div>
        )}
      </section>

      {review.summary.omittedUnsupportedDiagnosticCount > 0 && (
        <div className="mb-6 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
          <p className="text-xs text-muted-foreground">
            {review.summary.omittedUnsupportedDiagnosticCount} diagnostic record(s) were not promoted to findings
            because an exact supporting evidence span was unavailable.
          </p>
        </div>
      )}

      <AnimatePresence>
        {selectedFinding && (
          <FindingDetail
            repositoryId={review.repositoryId}
            finding={selectedFinding}
            onClose={() => setSelectedFindingId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function StatusPanel({ text }: { text: string }) {
  return (
    <div className="flex min-h-72 items-center justify-center gap-3">
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      <span className="text-sm text-muted-foreground">{text}</span>
    </div>
  );
}

function ErrorPanel({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center text-center">
      <p className="text-sm text-destructive">{message}</p>
      <button type="button" onClick={retry} className="mt-2 text-xs text-primary hover:underline">Retry</button>
    </div>
  );
}
