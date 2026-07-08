import type { DataSource, FeatureStatus } from '@/shared/types';

export interface FeatureState<T> {
  data: T | null;
  status: FeatureStatus;
  loading: boolean;
  error: string | null;
  empty: boolean;
  success: boolean;
  source: DataSource | null;
  retry: () => void;
  refresh: () => void;
}

export function createFeatureState<T>({
  data,
  status,
  error = null,
  source = null,
  retry,
  refresh,
}: {
  data: T | null;
  status: FeatureStatus;
  error?: string | null;
  source?: DataSource | null;
  retry: () => void;
  refresh: () => void;
}): FeatureState<T> {
  return {
    data,
    status,
    loading: status === 'loading',
    error,
    empty: status === 'empty',
    success: status === 'success',
    source,
    retry,
    refresh,
  };
}
