import { useCallback, useEffect, useState } from 'react';
import type { RepositorySource, FeatureStatus } from '@/shared/types';
import type { ArchitectureModel } from '@/shared/types/architecture';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useRepository } from '@/features/repositories/hooks/useRepository';
import { useArchitectureStore } from '../store';

export type ArchitectureEmptyReason = 'no-completed-repositories' | 'no-active-repository' | null;

export function useArchitecture() {
  const { activeRepository, completedRepositories } = useRepository();
  const setStoreModel = useArchitectureStore((state) => state.setModel);
  const storeModel = useArchitectureStore((state) => state.model);
  const [model, setModel] = useState<ArchitectureModel | null>(storeModel);
  const [source, setSource] = useState<RepositorySource | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    if (completedRepositories.length === 0) {
      setStatus('empty');
      setModel(null);
      setSource(null);
      setError(null);
      return;
    }

    if (!activeRepository || activeRepository.status !== 'completed') {
      setStatus('empty');
      setModel(null);
      setSource(null);
      setError(null);
      return;
    }

    let cancelled = false;

    async function loadArchitecture() {
      if (!activeRepository) return;
      setStatus('loading');
      setError(null);

      try {
        const nextModel = await backendService.fetchArchitecture(activeRepository);
        if (cancelled) return;

        setModel(nextModel);
        setStoreModel(nextModel);
        setSource(activeRepository.source);
        setStatus('success');
      } catch (caught) {
        if (cancelled) return;
        setModel(null);
        setSource(null);
        setError(getErrorMessage(caught));
        setStatus('error');
      }
    }

    void loadArchitecture();

    return () => {
      cancelled = true;
    };
  }, [activeRepository, completedRepositories.length, refreshKey, setStoreModel]);

  const emptyReason: ArchitectureEmptyReason =
    status === 'empty'
      ? completedRepositories.length === 0
        ? 'no-completed-repositories'
        : 'no-active-repository'
      : null;

  return {
    model,
    data: model,
    source,
    status,
    loading: status === 'loading',
    error,
    empty: status === 'empty',
    success: status === 'success',
    retry: refresh,
    refresh,
    activeRepository,
    completedRepositories,
    emptyReason,
  };
}
