import { useCallback, useEffect, useState } from 'react';
import type { DataSource, FeatureStatus } from '@/types';
import type { EngineeringReview } from '@/types/review';
import { backendService } from '@/services/backend';
import { getErrorMessage } from '@/services/api';
import { useRepository } from '@/features/repositories/hooks/useRepository';
import { useReviewStore } from '../store';

export type ReviewEmptyReason = 'no-completed-repositories' | 'no-active-repository' | null;

export function useReview() {
  const { activeRepository, completedRepositories } = useRepository();
  const { review: storeReview, setReview } = useReviewStore();
  const [review, setLocalReview] = useState<EngineeringReview | null>(storeReview);
  const [source, setSource] = useState<DataSource | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    if (completedRepositories.length === 0) {
      setStatus('empty');
      setLocalReview(null);
      setSource(null);
      setError(null);
      return;
    }

    if (!activeRepository || activeRepository.status !== 'completed') {
      setStatus('empty');
      setLocalReview(null);
      setSource(null);
      setError(null);
      return;
    }

    let cancelled = false;

    async function loadReview() {
      if (!activeRepository) return;
      setStatus('loading');
      setError(null);

      try {
        const nextReview = await backendService.fetchReview(activeRepository);
        if (cancelled) return;

        setLocalReview(nextReview);
        setReview(nextReview);
        setSource('real');
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
  }, [activeRepository, completedRepositories.length, refreshKey, setReview]);

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
    usingMockData: false,
  };
}
