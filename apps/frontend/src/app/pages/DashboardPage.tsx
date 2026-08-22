import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LayoutDashboard, FolderGit2, Upload, Activity, Clock, Github } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { MetricCard } from '@/shared/components/ui/MetricCard';
import { Badge } from '@/shared/components/ui/Badge';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { useRepositoryDashboard } from '@/features/repositories/hooks/useRepositoryDashboard';
import { repositoryStatusVariant } from '@/features/repositories/status';
import { formatFileSize } from '@/shared/utils/cn';
import type { Repository, RepositoryRevision } from '@/shared/types';

/**
 * Abbreviates the real revision identity already on the repository record
 * (#87, RFC-0001 §3) -- never invented. Both kinds render as `kind value`, the
 * same shape Insights and Engineering Review use, so a bare hex string is
 * never shown without saying what it is. The abbreviation is display-only: the
 * full immutable value is kept in the `title` at the call site, since a
 * 7-character prefix is not itself an identity.
 */
function shortRevisionLabel(revision: RepositoryRevision): string {
  if (revision.kind === 'git') return `git ${revision.value.slice(0, 7)}`;
  return `upload ${revision.value.replace(/^sha256:/, '').slice(0, 7)}`;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { repositories, metrics, selectRepository } = useRepositoryDashboard();

  // Most useful single fact: which repository's analysis is most current, as
  // of what revision -- derived only from fields the repository list (this
  // page's existing data) already carries, never a separate fetch.
  const mostRecentlyAnalysed = useMemo<(Repository & { analysedAt: string }) | null>(() => {
    const analysed = repositories.filter(
      (repo): repo is Repository & { analysedAt: string } => repo.status === 'completed' && Boolean(repo.analysedAt),
    );
    if (analysed.length === 0) return null;
    return analysed.reduce((latest, repo) =>
      new Date(repo.analysedAt).getTime() > new Date(latest.analysedAt).getTime() ? repo : latest,
    );
  }, [repositories]);

  if (repositories.length === 0) {
    return (
      <div>
        <PageHeader title="Dashboard" description="Your repository intelligence overview" />
        <EmptyState
          icon={LayoutDashboard}
          title="Welcome to PARTHA"
          description="Upload your first repository to start understanding any codebase in minutes. Get architecture insights, dependency graphs, and AI-powered explanations."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Dashboard" description="Your repository intelligence overview">
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_rgba(250,77,1,0.18)] hover:bg-primary/90 transition-colors"
        >
          <Upload className="h-3.5 w-3.5" />
          Upload
        </button>
      </PageHeader>

      {mostRecentlyAnalysed && (
        <p data-testid="latest-analysis-summary" className="mb-7 rounded-2xl border border-[#fa4d01]/15 bg-[#fff7f1] px-4 py-3 text-sm text-muted-foreground">
          Most recently analysed:{' '}
          <span className="font-medium text-foreground">{mostRecentlyAnalysed.name}</span>
          {' — '}
          {new Date(mostRecentlyAnalysed.analysedAt).toLocaleString()}
          {mostRecentlyAnalysed.revision && (
            <>
              {' at revision '}
              <code className="text-xs text-foreground" title={mostRecentlyAnalysed.revision.value}>
                {shortRevisionLabel(mostRecentlyAnalysed.revision)}
              </code>
            </>
          )}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard label="Repositories" value={metrics.totalRepositories} icon={FolderGit2} />
        <MetricCard label="Analysed" value={metrics.completedRepositories} icon={Activity} />
        <MetricCard label="Total Files" value={metrics.totalFiles} icon={LayoutDashboard} />
        <MetricCard label="Total Size" value={formatFileSize(metrics.totalSize)} icon={Upload} />
      </div>

      <div className="overflow-hidden rounded-3xl border border-[#fa4d01]/20 bg-card shadow-[0_14px_34px_rgba(48,21,47,0.05)]">
        <div className="border-b border-[#fa4d01]/15 px-6 py-5">
          <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-primary">System view</p>
          <h2 className="mt-1 text-lg font-semibold text-foreground">Repositories</h2>
        </div>
        <div className="divide-y divide-border">
          {repositories.map((repo, index) => (
            <motion.div
              key={repo.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              onClick={() => {
                selectRepository(repo);
                if (repo.status === 'analysing' || repo.status === 'cancelled') navigate(`/analysis/${repo.id}`);
                else navigate(`/repositories/${repo.id}`);
              }}
              className="flex min-w-0 flex-col items-start justify-between gap-3 px-5 py-4 hover:bg-[#fff7f1] cursor-pointer transition-colors sm:flex-row sm:items-center sm:px-6"
            >
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#fa4d01]/15 bg-[#dcecf2]">
                  {repo.source === 'github' ? (
                    <Github className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <FolderGit2 className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{repo.name}</p>
                  <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-2">
                    {repo.meta?.language && (
                      <span className="text-xs text-muted-foreground">{repo.meta.language}</span>
                    )}
                    {repo.meta?.framework && (
                      <span className="text-xs text-muted-foreground">/ {repo.meta.framework}</span>
                    )}
                    {!repo.meta && (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {new Date(repo.uploadedAt).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex max-w-full flex-wrap items-center gap-3 sm:justify-end">
                <DataSourceBadge source={repo.source} />
                {repo.meta && (
                  <span className="text-xs text-muted-foreground hidden sm:inline">
                    {repo.meta.totalFiles} files
                  </span>
                )}
                <Badge variant={repositoryStatusVariant[repo.status]}>{repo.status}</Badge>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
