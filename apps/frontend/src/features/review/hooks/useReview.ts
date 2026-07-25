import { useCallback, useEffect, useState } from 'react';
import type { RepositorySource, FeatureStatus } from '@/shared/types';
import type { EngineeringReview } from '@/shared/types/review';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useRepository } from '@/features/repositories/hooks/useRepository';
import { useReviewStore } from '../store';

export type ReviewEmptyReason = 'no-completed-repositories' | 'no-active-repository' | null;

export function useReview() {
  const { activeRepository, completedRepositories } = useRepository();
  const { setReview, resetForRepository } = useReviewStore();
  const [review, setLocalReview] = useState<EngineeringReview | null>(null);
  const [source, setSource] = useState<RepositorySource | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    if (completedRepositories.length === 0) {
      setStatus('empty');
      setLocalReview(null);
      setReview(null);
      setSource(null);
      setError(null);
      return;
    }

    if (!activeRepository || activeRepository.status !== 'completed') {
      setStatus('empty');
      setLocalReview(null);
      setReview(null);
      setSource(null);
      setError(null);
      return;
    }

    let cancelled = false;
    resetForRepository();
    setLocalReview(null);
    setSource(null);

    async function loadReview() {
      if (!activeRepository) return;
      setStatus('loading');
      setError(null);

      try {
        const nextReview = await backendService.fetchReview(activeRepository);
        if (cancelled) return;

        setLocalReview(nextReview);
        setReview(nextReview);
        setSource(activeRepository.source);
        setStatus('success');
      } catch (caught) {
        if (cancelled) return;
        setLocalReview(null);
        setSource(null);
        setError(getErrorMessage(caught));
        setStatus('error');
      }
    }

    void loadReview();

    return () => {
      cancelled = true;
    };
  }, [activeRepository, completedRepositories.length, refreshKey, resetForRepository, setReview]);

  const emptyReason: ReviewEmptyReason =
    status === 'empty'
      ? completedRepositories.length === 0
        ? 'no-completed-repositories'
        : 'no-active-repository'
      : null;

  return {
    review,
    data: review,
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
