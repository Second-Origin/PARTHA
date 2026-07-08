import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FolderGit2, Trash2, ExternalLink, Github, Upload as UploadIcon } from 'lucide-react';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { Badge } from '@/components/shared/Badge';
import { DataSourceBadge } from '@/components/shared/DataSourceBadge';
import { useRepository } from '@/features/repositories/hooks/useRepository';
import { repositoryStatusVariant } from '@/features/repositories/status';

export function RepositoriesPage() {
  const navigate = useNavigate();
  const { repositories, removeRepository, selectRepository } = useRepository();

  if (repositories.length === 0) {
    return (
      <div>
        <PageHeader title="Repositories" description="Manage your uploaded repositories" />
        <EmptyState
          icon={FolderGit2}
          title="No repositories yet"
          description="Upload a repository or import from GitHub to begin exploring its architecture, dependencies, and documentation."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Repositories" description="Manage your uploaded repositories">
        <button
          onClick={() => navigate('/upload')}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Upload New
        </button>
      </PageHeader>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider hidden sm:table-cell">Source</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider hidden md:table-cell">Language</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider hidden lg:table-cell">Files</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {repositories.map((repo, index) => (
              <motion.tr
                key={repo.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: index * 0.03 }}
                className="hover:bg-accent/30 transition-colors"
              >
                <td className="px-4 py-3">
                  <button
                    onClick={() => {
                      selectRepository(repo);
                      if (repo.status === 'analysing') navigate(`/analysis/${repo.id}`);
                      else navigate(`/repositories/${repo.id}`);
                    }}
                    className="text-sm font-medium text-foreground hover:text-primary transition-colors"
                  >
                    {repo.name}
                  </button>
                </td>
                <td className="px-4 py-3 hidden sm:table-cell">
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    {repo.source === 'github' ? (
                      <><Github className="h-3.5 w-3.5" /> GitHub</>
                    ) : (
                      <><UploadIcon className="h-3.5 w-3.5" /> Upload</>
                    )}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground hidden md:table-cell">
                  {repo.meta?.language || '-'}
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground hidden lg:table-cell">
                  {repo.meta?.totalFiles || '-'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Badge variant={repositoryStatusVariant[repo.status]}>{repo.status}</Badge>
                    <DataSourceBadge source={repo.dataSource} />
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => {
                        selectRepository(repo);
                        if (repo.status === 'analysing') navigate(`/analysis/${repo.id}`);
                        else navigate(`/repositories/${repo.id}`);
                      }}
                      className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => removeRepository(repo.id)}
                      className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
