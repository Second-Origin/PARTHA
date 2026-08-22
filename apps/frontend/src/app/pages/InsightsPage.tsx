import { Link, useNavigate } from 'react-router-dom';
import { BarChart3, ExternalLink, Info, ShieldCheck } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { useInsights } from '@/features/insights/hooks/useInsights';
import type { InsightBreakdown, InsightMetric } from '@/shared/types/insights';

export function InsightsPage() {
  const navigate = useNavigate();
  const insights = useInsights();

  if (insights.emptyReason === 'no-completed-repositories') {
    return (
      <div>
        <PageHeader title="Insights" description="Measurable facts for one exact repository revision" />
        <EmptyState
          icon={BarChart3}
          title="No repository insights available"
          description="Upload and analyse a repository to compute metrics from its sealed snapshot."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }
  if (insights.emptyReason === 'no-active-repository') {
    return (
      <div>
        <PageHeader title="Insights" description="Measurable facts for one exact repository revision" />
        <EmptyState
          icon={BarChart3}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to inspect its snapshot metrics."
        />
      </div>
    );
  }
  if (insights.loading) {
    return (
      <div className="flex min-h-72 items-center justify-center gap-3">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <span className="text-sm text-muted-foreground">Loading snapshot-backed repository insights...</span>
      </div>
    );
  }
  // A repository can be analysed yet still have no sealed ri.v1 snapshot
  // (#178, same 404 contract as Dependencies/Architecture). That must read as
  // "run analysis again", never as a generic, unguided error message.
  if (insights.noSnapshot) {
    return (
      <div>
        <PageHeader title="Insights" description="Measurable facts for one exact repository revision" />
        <EmptyState
          icon={BarChart3}
          title="No sealed snapshot yet"
          description="This repository has no sealed Repository Intelligence snapshot for its current revision. Analyse it again to generate one."
          action={{ label: 'Run analysis', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }
  if (insights.error) {
    return (
      <div className="flex min-h-72 flex-col items-center justify-center text-center">
        <p className="text-sm text-destructive">{insights.error}</p>
        <button type="button" onClick={insights.retry} className="mt-2 text-xs text-primary hover:underline">
          Retry
        </button>
      </div>
    );
  }
  if (!insights.data) return null;
  const data = insights.data;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Insights"
        description={`${data.repositoryName} · ${data.revisionKind} ${data.revisionValue}`}
      >
        <Link
          to="/architecture"
          className="inline-flex items-center gap-1 rounded-xl border border-[#fa4d01]/30 px-3 py-2 text-xs font-semibold hover:bg-[#fff1e9]"
        >
          Architecture <ExternalLink className="h-3 w-3" />
        </Link>
        <Link
          to="/review"
          className="inline-flex items-center gap-1 rounded-xl border border-[#fa4d01]/30 px-3 py-2 text-xs font-semibold hover:bg-[#fff1e9]"
        >
          Engineering Review <ExternalLink className="h-3 w-3" />
        </Link>
      </PageHeader>

      <div className="mb-5 flex items-start gap-2 rounded-2xl border border-primary/30 bg-primary/5 p-4">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p className="text-sm text-foreground">
          Every value below is defined and counted from the selected sealed snapshot. Missing assessments remain
          visibly unavailable; no legacy metadata is used.
        </p>
      </div>

      <section aria-label="Insights identity" className="mb-6 grid gap-3 rounded-3xl border border-[#fa4d01]/20 bg-card p-5 shadow-[0_14px_34px_rgba(48,21,47,0.04)] sm:grid-cols-2 lg:grid-cols-4">
        <Identity label="Snapshot" value={data.snapshotId} />
        <Identity label="Snapshot schema" value={data.snapshotSchemaVersion} />
        <Identity label="Manifest digest" value={data.manifestDigest} />
        <Identity label="Canonical graph hash" value={data.canonicalGraphHash} />
      </section>

      <section className="mb-7">
        <h2 className="mb-3 text-sm font-medium text-foreground">Defined metrics</h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.metrics.map((metric) => <MetricCard key={metric.id} metric={metric} />)}
        </div>
      </section>

      <div className="mb-7 grid gap-5 lg:grid-cols-2">
        <BreakdownCard title="Resolved relationships by predicate" items={data.relationshipsByPredicate} />
        <BreakdownCard title="Diagnostics by severity" items={data.diagnosticsBySeverity} />
        <BreakdownCard title="Language inventory" items={data.languages} />
        <section className="rounded-3xl border border-[#fa4d01]/20 bg-card p-5 shadow-[0_14px_34px_rgba(48,21,47,0.04)]">
          <h2 className="text-sm font-medium text-foreground">Diagnostics by code</h2>
          {data.diagnosticsByCode.length === 0 ? (
            <p className="mt-3 text-xs text-muted-foreground">No diagnostics were stored in this snapshot.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {data.diagnosticsByCode.map((item) => (
                <li key={item.key} className="flex items-center justify-between gap-3 text-xs">
                  <Link
                    to={`/review?diagnosticCode=${encodeURIComponent(item.key)}`}
                    className="font-mono text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                  >
                    {item.key}
                  </Link>
                  <span className="font-semibold text-foreground">{item.value}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="mb-7 rounded-3xl border border-[#fa4d01]/20 bg-card p-5 shadow-[0_14px_34px_rgba(48,21,47,0.04)]">
        <h2 className="text-sm font-medium text-foreground">Extractor inventory</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th className="pb-2 font-medium">Extractor</th>
                <th className="pb-2 font-medium">Version</th>
                <th className="pb-2 text-right font-medium">Evidence records</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#fa4d01]/10">
              {data.extractorSet.map((extractor) => (
                <tr key={`${extractor.name}@${extractor.version}`}>
                  <td className="py-2 font-mono text-foreground">{extractor.name}</td>
                  <td className="py-2 font-mono text-muted-foreground">{extractor.version || 'Not available'}</td>
                  <td className="py-2 text-right text-foreground">{extractor.evidenceRecordCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-8 flex items-start gap-2 rounded-2xl border border-[#fa4d01]/20 bg-card p-4">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div>
          <h2 className="text-sm font-medium text-foreground">Change over time</h2>
          <p className="mt-1 text-xs text-muted-foreground">{data.changeOverTime.message}</p>
        </div>
      </section>
    </div>
  );
}

function MetricCard({ metric }: { metric: InsightMetric }) {
  const value =
    metric.assessmentState === 'not_assessed'
      ? 'Not assessed'
      : metric.assessmentState === 'insufficient_evidence'
        ? 'Insufficient evidence'
        : metric.numerator !== null && metric.denominator !== null
          ? `${metric.numerator} / ${metric.denominator}`
          : String(metric.value ?? 'Not available');

  return (
    <article className="rounded-2xl border border-[#fa4d01]/20 bg-card p-4 shadow-[0_10px_24px_rgba(48,21,47,0.03)]">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-medium text-foreground">{metric.label}</h3>
        <span className="rounded-lg bg-[#fff1e9] px-2 py-1 text-[10px] text-muted-foreground">{metric.unit}</span>
      </div>
      <p className="mt-3 text-2xl font-semibold text-foreground">{value}</p>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{metric.definition}</p>
      <p className="mt-2 truncate font-mono text-[9px] text-muted-foreground" title={metric.id}>{metric.id}</p>
    </article>
  );
}

function BreakdownCard({ title, items }: { title: string; items: InsightBreakdown[] }) {
  return (
    <section className="rounded-3xl border border-[#fa4d01]/20 bg-card p-5 shadow-[0_14px_34px_rgba(48,21,47,0.04)]">
      <h2 className="text-sm font-medium text-foreground">{title}</h2>
      {items.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">No records are available for this breakdown.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={item.key} className="flex items-center justify-between gap-3 text-xs">
              <span className="capitalize text-muted-foreground">{item.label}</span>
              <span className="font-semibold text-foreground">{item.value}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Identity({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-2xs font-semibold uppercase tracking-[0.12em] text-primary">{label}</p>
      <p className="truncate font-mono text-xs text-foreground" title={value}>{value}</p>
    </div>
  );
}
