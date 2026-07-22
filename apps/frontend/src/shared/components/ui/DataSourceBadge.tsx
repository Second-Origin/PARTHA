import type { RepositorySource } from '@/shared/types';

interface DataSourceBadgeProps {
  source: RepositorySource | null | undefined;
}

export function DataSourceBadge({ source }: DataSourceBadgeProps) {
  if (!source) return null;

  return (
    <span className="text-xs text-muted-foreground" data-testid="repository-source">
      {source === 'github' ? 'GitHub repository' : 'Uploaded archive'}
    </span>
  );
}
