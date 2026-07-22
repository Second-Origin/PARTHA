import type { RepositorySource } from '@/shared/types';

const REPOSITORY_SOURCE_LABELS = {
  upload: 'Uploaded archive',
  github: 'GitHub repository',
} satisfies Record<RepositorySource, string>;

interface DataSourceBadgeProps {
  source: RepositorySource | null | undefined;
}

export function DataSourceBadge({ source }: DataSourceBadgeProps) {
  if (!source) return null;

  const label = REPOSITORY_SOURCE_LABELS[source];
  if (!label) return null;

  return (
    <span className="text-xs text-muted-foreground" data-testid="repository-source">
      {label}
    </span>
  );
}
