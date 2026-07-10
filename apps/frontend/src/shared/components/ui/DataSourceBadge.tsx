import type { DataSource } from '@/shared/types';

interface DataSourceBadgeProps {
  source: DataSource | null | undefined;
}

// This badge previously always rendered "Real data" regardless of its input.
// The `DataSource` type has a single value ('real') and the backend hard-codes
// data_source to "real", so the badge conveyed no information (audit F20). It now
// renders nothing. Call sites are intentionally left as harmless no-ops, and the
// data_source field/column is retained — dropping the NOT NULL column is a schema
// migration that is out of scope for this low-risk change.
export function DataSourceBadge({ source }: DataSourceBadgeProps) {
  void source;
  return null;
}
