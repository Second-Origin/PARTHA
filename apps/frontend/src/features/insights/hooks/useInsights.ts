import { useCallback, useEffect, useState } from 'react';
import type { FeatureStatus } from '@/shared/types';
import type { RepositoryInsights } from '@/shared/types/insights';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage, isApiError } from '@/shared/services/api';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export type InsightsEmptyReason = 'no-completed-repositories' | 'no-active-repository' | null;

export function useInsights() {
  const { activeRepository, completedRepositories } = useRepository();
  const [data, setData] = useState<RepositoryInsights | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  // A repository can be "completed" (analysed) yet still have no sealed ri.v1
  // snapshot yet, the same 404 Dependencies/Architecture already surface
  // (#178). That must never collapse into an unguided generic error message.
  const [noSnapshot, setNoSnapshot] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    if (completedRepositories.length === 0) {
      setData(null);
      setError(null);
      setNoSnapshot(false);
      setStatus('empty');
      return;
    }
    if (!activeRepository || activeRepository.status !== 'completed') {
      setData(null);
      setError(null);
      setNoSnapshot(false);
      setStatus('empty');
      return;
    }

    let cancelled = false;
    setData(null);
    setError(null);
    setNoSnapshot(false);
    setStatus('loading');
    void backendService
      .fetchInsights(activeRepository)
      .then((response) => {
        if (!cancelled) {
          setData(response);
          setStatus('success');
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setData(null);
          if (isApiError(caught) && caught.isNotFound) {
            setNoSnapshot(true);
          } else {
            setError(getErrorMessage(caught));
          }
          setStatus('error');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeRepository, completedRepositories.length, refreshKey]);

  const emptyReason: InsightsEmptyReason =
    status === 'empty'
      ? completedRepositories.length === 0
        ? 'no-completed-repositories'
        : 'no-active-repository'
      : null;

  return {
    data,
    activeRepository,
    completedRepositories,
    status,
    loading: status === 'loading',
    error,
    noSnapshot,
    empty: status === 'empty',
    success: status === 'success',
    emptyReason,
    retry: refresh,
    refresh,
  };
}
