import { useCallback, useEffect, useState } from 'react';
import type { DependencyGraphResponse } from '@/shared/services/api/types';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage, isApiError } from '@/shared/services/api';
import { useRepositoryFeatureStatus } from '@/shared/feature-state/useRepositoryFeatureStatus';

export function useDependencies() {
  const state = useRepositoryFeatureStatus();
  const [graph, setGraph] = useState<DependencyGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A repository can be "completed" (analysed) yet still have no sealed ri.v1
  // snapshot yet, the same 404 Architecture/Review/Insights already surface.
  // That must never be mistaken for a real, empty dependency inventory.
  const [noSnapshot, setNoSnapshot] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => {
    setError(null);
    setRefreshKey((key) => key + 1);
  }, []);

  useEffect(() => {
    if (!state.activeRepository || state.activeRepository.status !== 'completed') {
      setGraph(null);
      setError(null);
      setNoSnapshot(false);
      return;
    }

    let cancelled = false;
    async function loadDependencies() {
      if (!state.activeRepository) return;
      setLoading(true);
      setError(null);
      setNoSnapshot(false);
      try {
        const nextGraph = await backendService.fetchDependencyGraph(state.activeRepository.id);
        if (!cancelled) setGraph(nextGraph);
      } catch (caught) {
        if (cancelled) return;
        setGraph(null);
        if (isApiError(caught) && caught.isNotFound) {
          setNoSnapshot(true);
        } else {
          setError(getErrorMessage(caught));
        }
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
    noSnapshot,
    loading: state.loading || loading,
    error: state.error || error,
    retry: refresh,
    refresh,
    packageManager: state.activeRepository?.meta?.packageManager ?? null,
  };
}
