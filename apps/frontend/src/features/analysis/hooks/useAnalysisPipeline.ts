import { useCallback, useEffect, useRef, useState } from 'react';
import type { FeatureStatus, Repository } from '@/shared/types';
import { ANALYSIS_STAGES } from '@/shared/types';
import { backendService, hasBackend } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export function useAnalysisPipeline(repositoryId: string | undefined) {
  const { repositories } = useRepository();
  const completeAnalysis = useAppStore((state) => state.completeAnalysis);
  const failAnalysis = useAppStore((state) => state.failAnalysis);
  const cancelAnalysis = useAppStore((state) => state.cancelAnalysis);
  const updateRepository = useAppStore((state) => state.updateRepository);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const repository = repositories.find((repo) => repo.id === repositoryId) || null;
  const repositoryStatus = repository?.status;

  useEffect(() => {
    cancelledRef.current = false;
  }, [repositoryId]);

  const refresh = useCallback(() => {
    setError(null);
    setRefreshKey((key) => key + 1);
  }, []);

  useEffect(() => {
    if (!repositoryId || !repository) {
      setStatus('empty');
      return;
    }

    if (repository.status === 'completed') {
      setStatus('success');
      return;
    }

    if (repository.status === 'error') {
      setStatus('error');
      setError(repository.errorMessage || 'Analysis failed.');
      return;
    }

    if (cancelledRef.current) return;
    setStatus('loading');
    setError(null);

    if (hasBackend) {
      let cancelled = false;

      async function pollStatus() {
        if (!repositoryId || cancelled) return;
        try {
          const response = await backendService.fetchAnalysisStatus(repositoryId);
          if (!response || cancelled) return;

          const repositoryUpdates: Partial<Repository> = {
            dataSource: 'real',
            analysisStage: response.stage,
            analysisProgress: response.progress,
            errorMessage: response.error || undefined,
            analysedAt: response.completedAt || undefined,
          };

          if (response.status === 'failed') {
            failAnalysis(repositoryId, response.error || 'Analysis failed.');
            setStatus('error');
            setError(response.error || 'Analysis failed.');
            return;
          }

          if (response.status === 'completed') {
            completeAnalysis(repositoryId, repositoryUpdates);
            setStatus('success');
            return;
          }

          updateRepository(repositoryId, {
            ...repositoryUpdates,
            status: 'analysing',
          });
        } catch (caught) {
          setStatus('error');
          setError(getErrorMessage(caught));
        }
      }

      void pollStatus();
      const intervalId = window.setInterval(() => void pollStatus(), 1500);
      return () => {
        cancelled = true;
        window.clearInterval(intervalId);
      };
    }

    failAnalysis(repositoryId, 'Backend API is required for repository analysis.');
    setStatus('error');
    setError('Backend API is required for repository analysis.');
  }, [
    completeAnalysis,
    failAnalysis,
    refreshKey,
    repository,
    repositoryId,
    updateRepository,
  ]);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    if (timerRef.current) clearTimeout(timerRef.current);
    cancelAnalysis();
  }, [cancelAnalysis]);

  const currentStageIndex = ANALYSIS_STAGES.findIndex(
    (stage) => stage.key === repository?.analysisStage,
  );

  return {
    repository,
    stages: ANALYSIS_STAGES,
    currentStageIndex,
    status,
    loading: status === 'loading',
    error,
    empty: !repository,
    success: repositoryStatus === 'completed',
    source: repository?.dataSource || null,
    retry: refresh,
    refresh,
    cancel,
    completedRepositoryPath: repositoryStatus === 'completed' && repository ? `/repositories/${repository.id}` : null,
  };
}
