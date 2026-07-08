import type { DataSource } from '@/shared/types';
import { Badge } from './Badge';

interface DataSourceBadgeProps {
  source: DataSource | null | undefined;
}

export function DataSourceBadge({ source }: DataSourceBadgeProps) {
  if (!source) return null;
  return (
    <Badge variant="success">Real data</Badge>
  );
}
