import { useCallback, useEffect, useRef, useState } from 'react';
import type { FeatureStatus, Repository } from '@/shared/types';
import { ANALYSIS_STAGES } from '@/shared/types';
import { backendService, hasBackend } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import type { AnalysisJobStatus, AnalysisStatusResponse } from '@/shared/services/api/types';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export function useAnalysisPipeline(repositoryId: string | undefined) {
  const { repositories } = useRepository();
  const completeAnalysis = useAppStore((state) => state.completeAnalysis);
  const failAnalysis = useAppStore((state) => state.failAnalysis);
  const cancelAnalysis = useAppStore((state) => state.cancelAnalysis);
  const updateRepository = useAppStore((state) => state.updateRepository);
  const startedRef = useRef<string | null>(null);
  const pollingGenerationRef = useRef(0);
  const startInFlightRef = useRef<{
    repositoryId: string;
    promise: ReturnType<typeof backendService.startAnalysis>;
  } | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [jobStatus, setJobStatus] = useState<AnalysisJobStatus | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const repository = repositories.find((repo) => repo.id === repositoryId) || null;
  const repositoryStatus = repository?.status;

  useEffect(() => {
    pollingGenerationRef.current += 1;
    startedRef.current = null;
    startInFlightRef.current = null;
    setJobStatus(null);
    setCancelling(false);
  }, [repositoryId]);

  const applyJobResponse = useCallback(
    (response: AnalysisStatusResponse) => {
      if (!repositoryId) return;
      setJobStatus(response.status);

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

      if (response.status === 'cancelled') {
        cancelAnalysis();
        setCancelling(false);
        setStatus('idle');
        updateRepository(repositoryId, { ...repositoryUpdates, status: 'cancelled' });
        return;
      }

      updateRepository(repositoryId, {
        ...repositoryUpdates,
        status: 'analysing',
      });
    },
    [cancelAnalysis, completeAnalysis, failAnalysis, repositoryId, updateRepository],
  );

  const refresh = useCallback(() => {
    setError(null);
    setRefreshKey((key) => key + 1);
  }, []);

  // Known limitation: repository identity changes on each poll, so the interval is recreated.
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

    if (jobStatus === 'cancelled') {
      setStatus('idle');
      return;
    }
    setStatus('loading');
    setError(null);

    if (hasBackend) {
      let cancelled = false;
      const pollingGeneration = pollingGenerationRef.current;

      async function ensureStarted() {
        if (!repositoryId || repositoryStatus !== 'analysing' || startedRef.current === repositoryId) {
          return;
        }

        let inFlight = startInFlightRef.current;
        if (!inFlight || inFlight.repositoryId !== repositoryId) {
          inFlight = {
            repositoryId,
            promise: backendService.startAnalysis(repositoryId),
          };
          startInFlightRef.current = inFlight;
        }

        try {
          const response = await inFlight.promise;
          if (startInFlightRef.current === inFlight) {
            startedRef.current = response?.jobId ? repositoryId : null;
          }
        } finally {
          if (startInFlightRef.current === inFlight) {
            startInFlightRef.current = null;
          }
        }
      }

      async function pollStatus() {
        if (!repositoryId || cancelled) return;
        try {
          const response = await backendService.fetchAnalysisStatus(repositoryId);
          if (!response || cancelled || pollingGeneration !== pollingGenerationRef.current) return;

          if (response.status === 'queued' && response.jobId === null) {
            await ensureStarted();
            if (cancelled) return;
          } else if (response.jobId !== null) {
            startedRef.current = repositoryId;
          }

          applyJobResponse(response);
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
    applyJobResponse,
    failAnalysis,
    refreshKey,
    repository,
    repositoryId,
    repositoryStatus,
    jobStatus,
  ]);

  const cancel = useCallback(async () => {
    if (!repositoryId || !hasBackend || cancelling) return;
    setCancelling(true);
    setError(null);
    try {
      const response = await backendService.cancelAnalysis(repositoryId);
      if (response) applyJobResponse(response);
    } catch (caught) {
      setCancelling(false);
      setError(getErrorMessage(caught));
    }
  }, [applyJobResponse, cancelling, repositoryId]);

  const restart = useCallback(async () => {
    if (!repositoryId || !hasBackend) return;
    pollingGenerationRef.current += 1;
    setError(null);
    try {
      const response = await backendService.startAnalysis(repositoryId);
      if (response) {
        startedRef.current = repositoryId;
        updateRepository(repositoryId, {
          status: 'analysing',
          analysisStage: null,
          analysisProgress: 0,
          errorMessage: undefined,
          analysedAt: undefined,
        });
        setJobStatus(response.status);
      }
    } catch (caught) {
      setStatus('error');
      setError(getErrorMessage(caught));
    }
  }, [repositoryId, updateRepository]);

  const currentStageIndex = ANALYSIS_STAGES.findIndex(
    (stage) => stage.key === repository?.analysisStage,
  );

  return {
    repository,
    stages: ANALYSIS_STAGES,
    currentStageIndex,
    status,
    jobStatus,
    loading: status === 'loading',
    error,
    empty: !repository,
    success: repositoryStatus === 'completed',
    source: repository?.source || null,
    retry: refresh,
    refresh,
    cancel,
    restart,
    cancelling,
    canCancel: jobStatus === 'queued' || jobStatus === 'running',
    cancelled: jobStatus === 'cancelled',
    completedRepositoryPath: repositoryStatus === 'completed' && repository ? `/repositories/${repository.id}` : null,
  };
}
