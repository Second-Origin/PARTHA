import { useCallback, useEffect, useState } from 'react';
import type { RepositorySource, FeatureStatus } from '@/shared/types';
import type { EngineeringReview } from '@/shared/types/review';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage, isApiError } from '@/shared/services/api';
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
  // A repository can be "completed" (analysed) yet still have no sealed ri.v1
  // snapshot yet, the same 404 Dependencies/Architecture already surface
  // (#178). That must never collapse into an unguided generic error message.
  const [noSnapshot, setNoSnapshot] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    if (completedRepositories.length === 0) {
      setStatus('empty');
      setLocalReview(null);
      setReview(null);
      setSource(null);
      setError(null);
      setNoSnapshot(false);
      return;
    }

    if (!activeRepository || activeRepository.status !== 'completed') {
      setStatus('empty');
      setLocalReview(null);
      setReview(null);
      setSource(null);
      setError(null);
      setNoSnapshot(false);
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
      setNoSnapshot(false);

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
        if (isApiError(caught) && caught.isNotFound) {
          setNoSnapshot(true);
          setStatus('error');
        } else {
          setError(getErrorMessage(caught));
          setStatus('error');
        }
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
    noSnapshot,
    empty: status === 'empty',
    success: status === 'success',
    retry: refresh,
    refresh,
    activeRepository,
    completedRepositories,
    emptyReason,
  };
}
