import { useCallback, useEffect, useState } from 'react';
import type { DependencyGraphResponse } from '@/services/api/types';
import { backendService } from '@/services/backend';
import { getErrorMessage } from '@/services/api';
import { useRepositoryFeatureStatus } from '@/features/shared/useRepositoryFeatureStatus';

export function useDependencies() {
  const state = useRepositoryFeatureStatus();
  const [graph, setGraph] = useState<DependencyGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => {
    setError(null);
    setRefreshKey((key) => key + 1);
  }, []);

  useEffect(() => {
    if (!state.activeRepository || state.activeRepository.status !== 'completed') {
      setGraph(null);
      setError(null);
      return;
    }

    let cancelled = false;
    async function loadDependencies() {
      if (!state.activeRepository) return;
      setLoading(true);
      setError(null);
      try {
        const nextGraph = await backendService.fetchDependencyGraph(state.activeRepository.id);
        if (!cancelled) setGraph(nextGraph);
      } catch (caught) {
        if (!cancelled) setError(getErrorMessage(caught));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadDependencies();
    return () => {
      cancelled = true;
    };
  }, [refreshKey, state.activeRepository]);

  return {
    ...state,
    graph,
    loading: state.loading || loading,
    error: state.error || error,
    retry: refresh,
    refresh,
    packageManager: state.activeRepository?.meta?.packageManager || 'npm',
  };
}
