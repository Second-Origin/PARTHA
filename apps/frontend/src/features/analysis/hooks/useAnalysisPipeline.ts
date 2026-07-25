import { useCallback, useEffect, useRef, useState } from 'react';
import type { FeatureStatus, Repository } from '@/shared/types';
import { ANALYSIS_STAGES } from '@/shared/types';
import { backendService, hasBackend } from '@/shared/services/backend';
import { getErrorMessage, isNetworkError, isTimeoutError } from '@/shared/services/api';
import type { AnalysisJobStatus, AnalysisStatusResponse } from '@/shared/services/api/types';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export type ConnectionStatus = 'connected' | 'retrying' | 'lost';

// A dropped poll (laptop sleep, dev server restart, transient socket error) is
// not a job failure -- the durable job keeps running server-side. Retry with
// bounded backoff before surfacing a connectivity error, so a blip never reads
// as "Analysis Failed".
const MAX_NETWORK_RETRIES = 5;
const RETRY_BASE_DELAY_MS = 1000;
const RETRY_MAX_DELAY_MS = 15000;
const POLL_INTERVAL_MS = 1500;

export function getNetworkRetryDelayMs(attempt: number): number {
  return Math.min(RETRY_MAX_DELAY_MS, RETRY_BASE_DELAY_MS * 2 ** (attempt - 1));
}

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
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connected');

  const repository = repositories.find((repo) => repo.id === repositoryId) || null;
  const repositoryStatus = repository?.status;

  useEffect(() => {
    pollingGenerationRef.current += 1;
    startedRef.current = null;
    startInFlightRef.current = null;
    setJobStatus(null);
    setCancelling(false);
    setConnectionStatus('connected');
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
    setConnectionStatus('connected');

    if (hasBackend) {
      let cancelled = false;
      let networkRetryCount = 0;
      let timeoutId: number | undefined;
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

          networkRetryCount = 0;
          setConnectionStatus('connected');

          if (response.status === 'queued' && response.jobId === null) {
            await ensureStarted();
            if (cancelled) return;
          } else if (response.jobId !== null) {
            startedRef.current = repositoryId;
          }

          // A job the API itself reports as failed is a real, terminal outcome --
          // render it immediately, distinct from a dropped connection below.
          applyJobResponse(response);
        } catch (caught) {
          if (cancelled) return;

          if (isNetworkError(caught) || isTimeoutError(caught)) {
            networkRetryCount += 1;
            if (networkRetryCount > MAX_NETWORK_RETRIES) {
              // Retry budget exhausted: a connectivity problem, not a job
              // failure. Stop auto-polling; only a manual retry resumes it.
              setConnectionStatus('lost');
              return;
            }
            setConnectionStatus('retrying');
            timeoutId = window.setTimeout(() => void pollStatus(), getNetworkRetryDelayMs(networkRetryCount));
            return;
          }

          setStatus('error');
          setError(getErrorMessage(caught));
          return;
        }
        if (!cancelled) {
          timeoutId = window.setTimeout(() => void pollStatus(), POLL_INTERVAL_MS);
        }
      }

      void pollStatus();
      return () => {
        cancelled = true;
        if (timeoutId !== undefined) window.clearTimeout(timeoutId);
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
    connectionStatus,
    retryingConnection: connectionStatus === 'retrying',
    connectionLost: connectionStatus === 'lost',
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
