import { Navigate, useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Check, Loader2, Circle, XCircle, ArrowLeft, Ban, WifiOff, Clock } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { useAnalysisPipeline } from '@/features/analysis/hooks/useAnalysisPipeline';
import { cn } from '@/shared/utils/cn';

export function AnalysisPipelinePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const analysis = useAnalysisPipeline(id);
  const repo = analysis.repository;

  if (!repo) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <p className="text-sm text-muted-foreground">Repository not found.</p>
        <button
          onClick={() => navigate('/upload')}
          className="mt-4 text-sm text-primary hover:underline"
        >
          Go to Upload
        </button>
      </div>
    );
  }

  if (analysis.completedRepositoryPath) {
    return <Navigate to={analysis.completedRepositoryPath} replace />;
  }

  return (
    <div className="max-w-xl mx-auto">
      <PageHeader
        title="Analysing Repository"
        description={repo.name}
      >
        <DataSourceBadge source={analysis.source} />
      </PageHeader>

      <div className="rounded-xl border border-border bg-card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Progress
          </span>
          <span className="text-sm font-semibold text-foreground">
            {repo.analysisProgress}%
          </span>
        </div>
        <div className="h-2 rounded-full bg-muted overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-primary"
            initial={{ width: 0 }}
            animate={{ width: `${repo.analysisProgress}%` }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
          />
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <div className="space-y-0">
          {analysis.stages.map((stage, index) => {
            const isCompleted = index < analysis.currentStageIndex;
            const isCurrent = index === analysis.currentStageIndex;
            const isPending = index > analysis.currentStageIndex;
            const isLast = index === analysis.stages.length - 1;

            return (
              <div key={stage.key} className="relative">
                <div className="flex items-center gap-3 py-2.5">
                  <div className="relative z-10">
                    {isCompleted ? (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="flex h-6 w-6 items-center justify-center rounded-full bg-success/20"
                      >
                        <Check className="h-3.5 w-3.5 text-success" />
                      </motion.div>
                    ) : isCurrent ? (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/20">
                        <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
                      </div>
                    ) : (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted">
                        <Circle className="h-3 w-3 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                  <span
                    className={cn(
                      'text-sm transition-colors',
                      isCompleted && 'text-muted-foreground',
                      isCurrent && 'text-foreground font-medium',
                      isPending && 'text-muted-foreground/60'
                    )}
                  >
                    {stage.label}
                  </span>
                </div>
                {!isLast && (
                  <div
                    className={cn(
                      'absolute left-[11px] top-[34px] w-[2px] h-[14px]',
                      isCompleted ? 'bg-success/30' : 'bg-border'
                    )}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {analysis.retryingConnection && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-xl border border-warning/50 bg-warning/5 p-4 flex items-start gap-3"
          role="status"
        >
          <WifiOff className="h-5 w-5 text-warning shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-warning">Connection lost — retrying…</p>
            <p className="text-xs text-warning/80 mt-0.5">
              Analysis is still running. Reconnecting to check its progress.
            </p>
          </div>
        </motion.div>
      )}

      {analysis.connectionLost && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-xl border border-warning/50 bg-warning/5 p-4 flex items-start gap-3"
          role="alert"
        >
          <WifiOff className="h-5 w-5 text-warning shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-warning">Connection lost</p>
            <p className="text-xs text-warning/80 mt-0.5">
              Cannot reach the PARTHA backend. The analysis job itself keeps running on the server — this
              only affects checking its progress here.
            </p>
            <button
              type="button"
              onClick={() => analysis.retry()}
              className="mt-2 text-xs text-primary hover:underline"
            >
              Retry connection
            </button>
          </div>
        </motion.div>
      )}

      {/* Suppressed once cancelled: the disabled, countdown-labelled Restart
          button below already communicates the same cooldown, and showing
          both at once would be a redundant, slightly confusing double banner. */}
      {analysis.rateLimited && !analysis.cancelled && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-xl border border-warning/50 bg-warning/5 p-4 flex items-start gap-3"
          role="status"
        >
          <Clock className="h-5 w-5 text-warning shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-warning">
              {analysis.rateLimitSecondsRemaining !== null
                ? `Too many requests — retrying automatically in ${analysis.rateLimitSecondsRemaining}s`
                : 'Still rate limited'}
            </p>
            <p className="text-xs text-warning/80 mt-0.5">
              Analysis is still running server-side. This is a temporary rate limit, not a failure —
              {analysis.rateLimitSecondsRemaining !== null
                ? ' checking progress will resume automatically.'
                : ' automatic retries were exhausted. Try again once the limit clears.'}
            </p>
            {analysis.rateLimitSecondsRemaining === null && (
              <button
                type="button"
                onClick={() => analysis.retry()}
                className="mt-2 text-xs text-primary hover:underline"
              >
                Retry now
              </button>
            )}
          </div>
        </motion.div>
      )}

      {(repo.status === 'error' || analysis.error) && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-xl border border-destructive/50 bg-destructive/5 p-4 flex items-start gap-3"
        >
          <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-destructive">Analysis Failed</p>
            <p className="text-xs text-destructive/80 mt-0.5">
              {repo.errorMessage || analysis.error || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => navigate('/upload')}
              className="mt-2 text-xs text-primary hover:underline"
            >
              Try again
            </button>
          </div>
        </motion.div>
      )}

      {analysis.cancelled && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-xl border border-border bg-muted/40 p-4 flex items-start gap-3"
          role="status"
        >
          <Ban className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">Analysis cancelled</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              No further analysis work will run for this job.
            </p>
            <button
              type="button"
              onClick={() => void analysis.restart()}
              disabled={analysis.rateLimitSecondsRemaining !== null}
              className="mt-2 text-xs text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted-foreground disabled:no-underline"
            >
              {analysis.rateLimitSecondsRemaining !== null
                ? `Restart analysis (wait ${analysis.rateLimitSecondsRemaining}s)`
                : 'Restart analysis'}
            </button>
          </div>
        </motion.div>
      )}

      <div className="mt-6 flex items-center justify-between gap-4">
        <button
          onClick={() => navigate('/repositories')}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to repositories
        </button>
        {analysis.canCancel && (
          <button
            type="button"
            onClick={() => void analysis.cancel()}
            disabled={analysis.cancelling}
            className="inline-flex items-center gap-2 rounded-lg border border-destructive/40 px-3 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {analysis.cancelling ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Ban className="h-4 w-4" />
            )}
            {analysis.cancelling ? 'Cancelling…' : 'Cancel analysis'}
          </button>
        )}
      </div>
    </div>
  );
}
