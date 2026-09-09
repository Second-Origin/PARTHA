import { useCallback, useEffect, useState } from 'react';
import type { FeatureStatus } from '@/shared/types';
import type { RepositoryLineageResponse } from '@/shared/services/api/types';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';

export function useRepositoryLineage(repositoryId: string | undefined) {
  const [data, setData] = useState<RepositoryLineageResponse | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    if (!repositoryId) {
      setData(null);
      setError(null);
      setStatus('empty');
      return;
    }

    let cancelled = false;
    setData(null);
    setError(null);
    setStatus('loading');
    void backendService
      .fetchRepositoryLineage(repositoryId)
      .then((response) => {
        if (!cancelled) {
          setData(response);
          setStatus('success');
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setData(null);
          setError(getErrorMessage(caught));
          setStatus('error');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [repositoryId, refreshKey]);

  return {
    data,
    entries: data?.entries ?? [],
    isLineaged: data?.isLineaged ?? false,
    status,
    loading: status === 'loading',
    error,
    empty: status === 'empty',
    success: status === 'success',
    retry: refresh,
    refresh,
  };
}
