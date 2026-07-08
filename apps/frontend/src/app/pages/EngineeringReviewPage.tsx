import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { useReviewStore } from '@/features/review/store';
import { useReview } from '@/features/review/hooks/useReview';
import { ScoreCard, OverallScoreRing } from '@/features/review/components/ScoreCard';
import { FindingCard } from '@/features/review/components/FindingCard';
import { FindingDetail } from '@/features/review/components/FindingDetail';
import { ReviewFilters } from '@/features/review/components/ReviewFilters';
import { Roadmap } from '@/features/review/components/Roadmap';
import { ReviewExport } from '@/features/review/components/ReviewExport';
import { cn } from '@/shared/utils/cn';

export function EngineeringReviewPage() {
  const navigate = useNavigate();
  const reviewState = useReview();
  const {
    review,
    selectedFindingId,
    setSelectedFindingId,
    setFilterCategory,
    setFilterSeverity,
    filteredFindings,
  } = useReviewStore();
  const activeReview = reviewState.review || review;

  const findings = filteredFindings();
  const selectedFinding = useMemo(
    () => activeReview?.findings.find((f) => f.id === selectedFindingId) || null,
    [activeReview, selectedFindingId]
  );

  if (reviewState.emptyReason === 'no-completed-repositories') {
    return (
      <div className="h-full flex flex-col">
        <EmptyState
          icon={ShieldCheck}
          title="No engineering review available"
          description="Upload and analyse a repository to generate its engineering review. The review is built from repository analysis data."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (reviewState.emptyReason === 'no-active-repository') {
    return (
      <div className="h-full flex flex-col">
        <EmptyState
          icon={ShieldCheck}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to view its engineering review."
        />
      </div>
    );
  }

  if (reviewState.error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-destructive mb-2">{reviewState.error}</p>
          <button onClick={reviewState.retry} className="text-xs text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (reviewState.loading || !activeReview) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span className="text-sm text-muted-foreground">Loading engineering review...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] -m-6">
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        <div className="max-w-5xl">
          <div className="flex items-center justify-between mb-6">
            <PageHeader
              title="Engineering Review"
              description={`Automated audit for ${activeReview.repositoryName}`}
            >
              <DataSourceBadge source={reviewState.source} />
            </PageHeader>
            <ReviewExport review={activeReview} />
          </div>

          {/* Executive Summary */}
          <section className="mb-8">
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex flex-col lg:flex-row items-start lg:items-center gap-6">
                <OverallScoreRing
                  score={activeReview.summary.overallScore}
                  trend={activeReview.summary.overallTrend}
                  totalFindings={activeReview.summary.totalFindings}
                  criticalCount={activeReview.summary.criticalCount}
                  highCount={activeReview.summary.highCount}
                />
                <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <SummaryPill
                    icon={AlertTriangle}
                    label="Critical"
                    count={activeReview.summary.criticalCount}
                    color="text-red-400"
                    bg="bg-red-500/10"
                  />
                  <SummaryPill
                    icon={AlertCircle}
                    label="High"
                    count={activeReview.summary.highCount}
                    color="text-orange-400"
                    bg="bg-orange-500/10"
                  />
                  <SummaryPill
                    icon={Info}
                    label="Medium"
                    count={activeReview.summary.mediumCount}
                    color="text-amber-400"
                    bg="bg-amber-500/10"
                  />
                  <SummaryPill
                    icon={CheckCircle2}
                    label="Low"
                    count={activeReview.summary.lowCount}
                    color="text-blue-400"
                    bg="bg-blue-500/10"
                  />
                </div>
              </div>
            </div>
          </section>

          {/* Health Scores */}
          <section className="mb-8">
            <h2 className="text-sm font-medium text-foreground mb-3">Health Scores</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {activeReview.scores.map((score) => (
                <ScoreCard
                  key={score.category}
                  score={score}
                  onClick={() => {
                    setFilterCategory(score.category);
                    setFilterSeverity('all');
                  }}
                />
              ))}
            </div>
          </section>

          {/* Findings */}
          <section className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-foreground">Findings</h2>
              <span className="text-xs text-muted-foreground">{findings.length} results</span>
            </div>
            <ReviewFilters />
            <div className="mt-4 space-y-2">
              {findings.length === 0 ? (
                <div className="rounded-lg border border-border bg-card p-8 text-center">
                  <CheckCircle2 className="h-8 w-8 text-green-400 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No findings match the current filters</p>
                </div>
              ) : (
                findings.map((finding) => (
                  <motion.div
                    key={finding.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <FindingCard
                      finding={finding}
                      isSelected={selectedFindingId === finding.id}
                      onClick={() => setSelectedFindingId(
                        selectedFindingId === finding.id ? null : finding.id
                      )}
                    />
                  </motion.div>
                ))
              )}
            </div>
          </section>

          {/* Roadmap */}
          <section className="mb-8">
            <Roadmap steps={activeReview.roadmap} />
          </section>
        </div>
      </div>

      {/* Detail Panel */}
      <AnimatePresence>
        {selectedFinding && (
          <FindingDetail
            finding={selectedFinding}
            onClose={() => setSelectedFindingId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function SummaryPill({
  icon: Icon,
  label,
  count,
  color,
  bg,
}: {
  icon: typeof AlertTriangle;
  label: string;
  count: number;
  color: string;
  bg: string;
}) {
  return (
    <div className={cn('rounded-lg border border-border p-3 text-center', count > 0 && bg)}>
      <Icon className={cn('h-4 w-4 mx-auto mb-1', count > 0 ? color : 'text-muted-foreground/50')} />
      <p className={cn('text-lg font-bold', count > 0 ? color : 'text-muted-foreground/50')}>{count}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  );
}
