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

export function DashboardPage() {
  const navigate = useNavigate();
  const { repositories, metrics, selectRepository } = useRepositoryDashboard();

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
          className="flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Upload className="h-3.5 w-3.5" />
          Upload
        </button>
      </PageHeader>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard label="Repositories" value={metrics.totalRepositories} icon={FolderGit2} />
        <MetricCard label="Analysed" value={metrics.completedRepositories} icon={Activity} />
        <MetricCard label="Total Files" value={metrics.totalFiles} icon={LayoutDashboard} />
        <MetricCard label="Total Size" value={formatFileSize(metrics.totalSize)} icon={Upload} />
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-medium text-foreground">Repositories</h2>
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
                if (repo.status === 'analysing') navigate(`/analysis/${repo.id}`);
                else navigate(`/repositories/${repo.id}`);
              }}
              className="flex items-center justify-between px-5 py-3.5 hover:bg-accent/30 cursor-pointer transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                  {repo.source === 'github' ? (
                    <Github className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <FolderGit2 className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{repo.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
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
              <div className="flex items-center gap-3">
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
