import { useCallback, useEffect, useRef, useState } from 'react';
import type { FeatureStatus, Repository } from '@/shared/types';
import { ANALYSIS_STAGES } from '@/shared/types';
import { backendService, hasBackend } from '@/shared/services/backend';
import { getErrorMessage, isApiError, isNetworkError, isTimeoutError } from '@/shared/services/api';
import type { AnalysisJobStatus, AnalysisStatusResponse } from '@/shared/services/api/types';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export type ConnectionStatus = 'connected' | 'retrying' | 'lost' | 'rate-limited';

// A dropped poll (laptop sleep, dev server restart, transient socket error) is
// not a job failure -- the durable job keeps running server-side. Retry with
// bounded backoff before surfacing a connectivity error, so a blip never reads
// as "Analysis Failed".
const MAX_NETWORK_RETRIES = 5;
const RETRY_BASE_DELAY_MS = 1000;
const RETRY_MAX_DELAY_MS = 15000;
const POLL_INTERVAL_MS = 1500;

// A 429 is transient, not a job failure (#169): the durable job keeps running
// server-side exactly as it does for a dropped connection above. Wait exactly
// as long as the server's Retry-After says (falling back to a fixed default
// only when the server sent none) instead of hammering it with fixed backoff,
// which is itself a retry-storm risk. Bounded on both count and per-wait
// duration so a misconfigured or hostile Retry-After can't stall the UI.
export const MAX_RATE_LIMIT_AUTO_RETRIES = 3;
export const DEFAULT_RATE_LIMIT_RETRY_SECONDS = 30;
export const RATE_LIMIT_MAX_WAIT_SECONDS = 120;

export function getNetworkRetryDelayMs(attempt: number): number {
  return Math.min(RETRY_MAX_DELAY_MS, RETRY_BASE_DELAY_MS * 2 ** (attempt - 1));
}

export function boundedRateLimitWaitSeconds(retryAfterSeconds: number | null): number {
  return Math.min(RATE_LIMIT_MAX_WAIT_SECONDS, Math.max(1, Math.round(retryAfterSeconds ?? DEFAULT_RATE_LIMIT_RETRY_SECONDS)));
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
  // Countdown to the next automatic (or earliest allowed manual) retry while
  // rate-limited; `null` means either "not rate-limited" or "the bounded
  // auto-retry budget is exhausted and a manual retry is available now".
  const [rateLimitSecondsRemaining, setRateLimitSecondsRemaining] = useState<number | null>(null);
  const rateLimitIntervalRef = useRef<number | undefined>(undefined);

  const repository = repositories.find((repo) => repo.id === repositoryId) || null;
  const repositoryStatus = repository?.status;
  const repositoryErrorMessage = repository?.errorMessage;

  const clearRateLimitCooldown = useCallback(() => {
    window.clearInterval(rateLimitIntervalRef.current);
    rateLimitIntervalRef.current = undefined;
    setRateLimitSecondsRemaining(null);
  }, []);

  // Shared by the passive poller and the manual restart button so both sides
  // of "prevent retry storms" (bounded auto-retry, disabled manual retry)
  // count down the same way.
  const startRateLimitCooldown = useCallback((seconds: number, onElapsed: () => void) => {
    window.clearInterval(rateLimitIntervalRef.current);
    const bounded = boundedRateLimitWaitSeconds(seconds);
    setConnectionStatus('rate-limited');
    setRateLimitSecondsRemaining(bounded);
    let remaining = bounded;
    rateLimitIntervalRef.current = window.setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        window.clearInterval(rateLimitIntervalRef.current);
        rateLimitIntervalRef.current = undefined;
        setRateLimitSecondsRemaining(null);
        onElapsed();
      } else {
        setRateLimitSecondsRemaining(remaining);
      }
    }, 1000);
  }, []);

  useEffect(() => {
    pollingGenerationRef.current += 1;
    startedRef.current = null;
    startInFlightRef.current = null;
    setJobStatus(null);
    setCancelling(false);
    setConnectionStatus('connected');
    clearRateLimitCooldown();
  }, [repositoryId, clearRateLimitCooldown]);

  // The cooldown timer must not keep ticking (or ever fire) after unmount.
  useEffect(() => {
    return () => clearRateLimitCooldown();
  }, [clearRateLimitCooldown]);

  const applyJobResponse = useCallback(
    (response: AnalysisStatusResponse) => {
      if (!repositoryId) return;
      setJobStatus(response.status);

      const repositoryUpdates: Partial<Repository> = {
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

  useEffect(() => {
    if (!repositoryId || !repositoryStatus) {
      setStatus('empty');
      return;
    }

    if (repositoryStatus === 'completed') {
      setStatus('success');
      return;
    }

    if (repositoryStatus === 'error') {
      setStatus('error');
      setError(repositoryErrorMessage || 'Analysis failed.');
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
      let rateLimitRetryCount = 0;
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
          rateLimitRetryCount = 0;
          clearRateLimitCooldown();
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

          // Stop the loop here instead of relying on the surrounding effect to
          // tear it down on the next render: the poll loop owns its own
          // lifecycle, so a terminal outcome never schedules another request.
          if (response.status === 'completed' || response.status === 'failed' || response.status === 'cancelled') {
            return;
          }
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

          if (isApiError(caught) && caught.isRateLimited) {
            rateLimitRetryCount += 1;
            if (rateLimitRetryCount > MAX_RATE_LIMIT_AUTO_RETRIES) {
              // Bounded auto-retry budget exhausted. This was never a job
              // failure -- stay in the rate-limited state (not "Analysis
              // Failed") with the countdown cleared, so retry() (the same
              // manual action as connection-lost recovery) can resume it.
              setRateLimitSecondsRemaining(null);
              setConnectionStatus('rate-limited');
              return;
            }
            startRateLimitCooldown(caught.retryAfterSeconds ?? DEFAULT_RATE_LIMIT_RETRY_SECONDS, () => {
              if (!cancelled) void pollStatus();
            });
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
        clearRateLimitCooldown();
      };
    }

    failAnalysis(repositoryId, 'Backend API is required for repository analysis.');
    setStatus('error');
    setError('Backend API is required for repository analysis.');
  }, [
    applyJobResponse,
    clearRateLimitCooldown,
    failAnalysis,
    refreshKey,
    repositoryErrorMessage,
    repositoryId,
    repositoryStatus,
    startRateLimitCooldown,
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
    // A cooldown already in progress means a manual click here would be
    // exactly the retry-storming #169 exists to prevent -- the button that
    // triggers this is disabled for the same reason, this is defense in depth.
    if (!repositoryId || !hasBackend || rateLimitSecondsRemaining !== null) return;
    pollingGenerationRef.current += 1;
    setError(null);
    try {
      const response = await backendService.startAnalysis(repositoryId);
      if (response) {
        startedRef.current = repositoryId;
        clearRateLimitCooldown();
        setConnectionStatus('connected');
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
      if (isApiError(caught) && caught.isRateLimited) {
        // Transient, not terminal: start a cooldown (disabling the manual
        // retry trigger) instead of a repeatable "Analysis Failed" bounce.
        startRateLimitCooldown(caught.retryAfterSeconds ?? DEFAULT_RATE_LIMIT_RETRY_SECONDS, () => {});
        return;
      }
      setStatus('error');
      setError(getErrorMessage(caught));
    }
  }, [clearRateLimitCooldown, rateLimitSecondsRemaining, repositoryId, startRateLimitCooldown, updateRepository]);

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
    rateLimited: connectionStatus === 'rate-limited',
    rateLimitSecondsRemaining,
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
