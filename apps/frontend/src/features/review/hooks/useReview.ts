import { useCallback, useEffect, useRef, useState } from 'react';
import type { RepositorySource, FeatureStatus } from '@/shared/types';
import type { EngineeringReview } from '@/shared/types/review';
import type { ReviewQuery } from '@/shared/services/api/review';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage, isApiError } from '@/shared/services/api';
import { useRepository } from '@/features/repositories/hooks/useRepository';
import { useReviewStore, FINDINGS_PAGE_SIZE } from '../store';

export type ReviewEmptyReason = 'no-completed-repositories' | 'no-active-repository' | null;

export function useReview() {
  const { activeRepository, completedRepositories } = useRepository();
  const { setReview, appendFindings, resetForRepository, filterCategory, filterSeverity, filterDiagnosticCode } =
    useReviewStore();
  const [review, setLocalReview] = useState<EngineeringReview | null>(null);
  const [source, setSource] = useState<RepositorySource | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  // A repository can be "completed" (analysed) yet still have no sealed ri.v1
  // snapshot yet, the same 404 Dependencies/Architecture already surface
  // (#178). That must never collapse into an unguided generic error message.
  const [noSnapshot, setNoSnapshot] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const previousRepositoryId = useRef<string | null>(null);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  const query: ReviewQuery = {
    category: filterCategory === 'all' ? undefined : filterCategory,
    severity: filterSeverity === 'all' ? undefined : filterSeverity,
    diagnosticCode: filterDiagnosticCode ?? undefined,
  };
  const queryKey = JSON.stringify(query);

  useEffect(() => {
    if (completedRepositories.length === 0) {
      previousRepositoryId.current = null;
      setStatus('empty');
      setLocalReview(null);
      setReview(null);
      setSource(null);
      setError(null);
      setNoSnapshot(false);
      return;
    }

    if (!activeRepository || activeRepository.status !== 'completed') {
      previousRepositoryId.current = null;
      setStatus('empty');
      setLocalReview(null);
      setReview(null);
      setSource(null);
      setError(null);
      setNoSnapshot(false);
      return;
    }

    // A repository switch resets filters and selection; a filter change or an
    // explicit retry of the same repository must not (the user just chose
    // that filter, or is retrying in place).
    const repositoryChanged = previousRepositoryId.current !== activeRepository.id;
    previousRepositoryId.current = activeRepository.id;
    const effectiveQuery = repositoryChanged
      ? { category: undefined, severity: undefined, diagnosticCode: undefined }
      : query;
    if (repositoryChanged) resetForRepository();

    let cancelled = false;
    setLocalReview(null);
    setSource(null);

    async function loadReview() {
      if (!activeRepository) return;
      setStatus('loading');
      setError(null);
      setNoSnapshot(false);

      try {
        const nextReview = await backendService.fetchReview(activeRepository, {
          ...effectiveQuery,
          offset: 0,
          limit: FINDINGS_PAGE_SIZE,
        });
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRepository, completedRepositories.length, refreshKey, queryKey, resetForRepository, setReview]);

  const loadMore = useCallback(async () => {
    if (!activeRepository || !review || loadingMore) return;
    setLoadingMore(true);
    try {
      const nextPage = await backendService.fetchReview(activeRepository, {
        ...query,
        offset: review.findings.length,
        limit: FINDINGS_PAGE_SIZE,
      });
      appendFindings(nextPage.findings, nextPage.pagination);
      setLocalReview((current) =>
        current
          ? { ...current, findings: [...current.findings, ...nextPage.findings], pagination: nextPage.pagination }
          : current,
      );
    } catch {
      // A failed "load more" leaves the already-loaded page intact; the user
      // can retry the action itself rather than losing everything to a
      // generic full-page error.
    } finally {
      setLoadingMore(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRepository, review, loadingMore, appendFindings, queryKey]);

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
    loadMore,
    loadingMore,
    activeRepository,
    completedRepositories,
    emptyReason,
  };
}
