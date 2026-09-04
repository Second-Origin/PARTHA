import { Link } from 'react-router-dom';
import { GitCommitHorizontal, Fingerprint, Loader2, TriangleAlert } from 'lucide-react';
import { Badge } from '@/shared/components/ui/Badge';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { repositoryStatusVariant } from '@/features/repositories/status';
import { useRepositoryLineage } from '@/features/repositories/hooks/useRepositoryLineage';
import { cn } from '@/shared/utils/cn';

interface RepositoryLineageHistoryProps {
  repositoryId: string;
}

export function RepositoryLineageHistory({ repositoryId }: RepositoryLineageHistoryProps) {
  const { entries, isLineaged, loading, error, retry } = useRepositoryLineage(repositoryId);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={TriangleAlert}
        title="Couldn't load history"
        description={error}
        action={{ label: 'Try again', onClick: retry }}
      />
    );
  }

  return (
    <div className="space-y-4">
      {!isLineaged && (
        <p className="text-sm text-muted-foreground">
          This is a standalone import — repeated GitHub imports of the same repository and branch are grouped into a
          shared history; a one-off upload or an unresolved-ref import never gets one.
        </p>
      )}
      <ol className="space-y-3">
        {entries.map((entry) => (
          <li key={entry.repositoryId}>
            <div
              className={cn(
                'flex items-center justify-between gap-4 rounded-2xl border p-4 shadow-[0_10px_24px_hsl(var(--foreground)/0.03)]',
                entry.isCurrent ? 'border-primary/40 bg-primary/5' : 'border-primary/20 bg-card',
              )}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  {entry.sequence !== null && (
                    <span className="text-2xs font-semibold uppercase tracking-[0.12em] text-primary">
                      #{entry.sequence}
                    </span>
                  )}
                  <p className="truncate text-sm font-semibold text-foreground">{entry.name}</p>
                  {entry.isCurrent && <Badge variant="info">Viewing</Badge>}
                  <Badge variant={repositoryStatusVariant[entry.status]}>{entry.status}</Badge>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {entry.revision && (
                    <span className="flex items-center gap-1 font-mono">
                      {entry.revision.kind === 'git' ? (
                        <GitCommitHorizontal className="h-3 w-3" />
                      ) : (
                        <Fingerprint className="h-3 w-3" />
                      )}
                      {entry.revision.value.slice(0, 12)}
                    </span>
                  )}
                  <span>{new Date(entry.uploadedAt).toLocaleString()}</span>
                </div>
              </div>
              {!entry.isCurrent && (
                <Link
                  to={`/repositories/${entry.repositoryId}`}
                  className="shrink-0 text-xs font-semibold text-primary hover:underline"
                >
                  View
                </Link>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
