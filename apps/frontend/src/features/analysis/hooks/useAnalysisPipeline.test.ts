import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { backendService } from '@/shared/services/backend';
import { NetworkError, TimeoutError } from '@/shared/services/api';
import type { AnalysisStartResponse } from '@/shared/services/api/types';
import type { Repository } from '@/shared/types';
import { getNetworkRetryDelayMs, useAnalysisPipeline } from './useAnalysisPipeline';

const repositoryState = vi.hoisted(() => ({ repositories: [] as Repository[] }));

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({ repositories: repositoryState.repositories }),
}));

const repository: Repository = {
  id: 'repo-1',
  name: 'sample',
  source: 'upload',
  size: 10,
  fileCount: 1,
  status: 'analysing',
  dataSource: 'real',
  analysisStage: 'reading-structure',
  analysisProgress: 25,
  uploadedAt: '2026-07-22T08:00:00Z',
  meta: null,
  fileTree: [],
};

describe('useAnalysisPipeline', () => {
  beforeEach(() => {
    repositoryState.repositories = [repository];
    useAppStore.setState({ repositories: [repository], analysisRunning: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('requests server cancellation and stops in the cancelled terminal state', async () => {
    const start = vi.spyOn(backendService, 'startAnalysis');
    vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
      repositoryId: repository.id,
      status: 'running',
      jobId: 'job-1',
      stage: 'reading-structure',
      progress: 25,
      startedAt: '2026-07-22T08:00:01Z',
      completedAt: null,
      error: null,
    });
    const cancel = vi.spyOn(backendService, 'cancelAnalysis').mockResolvedValue({
      repositoryId: repository.id,
      status: 'cancelled',
      jobId: 'job-1',
      stage: 'reading-structure',
      progress: 25,
      startedAt: '2026-07-22T08:00:01Z',
      completedAt: '2026-07-22T08:00:02Z',
      error: null,
    });

    const hook = renderHook(() => useAnalysisPipeline(repository.id));
    await waitFor(() => expect(hook.result.current.jobStatus).toBe('running'));
    expect(hook.result.current.canCancel).toBe(true);

    await act(async () => {
      await hook.result.current.cancel();
    });

    expect(cancel).toHaveBeenCalledWith(repository.id);
    expect(hook.result.current.jobStatus).toBe('cancelled');
    expect(hook.result.current.cancelled).toBe(true);
    expect(hook.result.current.canCancel).toBe(false);
    expect(useAppStore.getState().analysisRunning).toBe(false);
    expect(useAppStore.getState().repositories[0].status).toBe('cancelled');
    expect(start).not.toHaveBeenCalled();
  });

  it('restarts a cancelled repository without another upload', async () => {
    vi.spyOn(backendService, 'fetchAnalysisStatus')
      .mockResolvedValueOnce({
        repositoryId: repository.id,
        status: 'cancelled',
        jobId: 'job-1',
        stage: 'reading-structure',
        progress: 25,
        startedAt: '2026-07-22T08:00:01Z',
        completedAt: '2026-07-22T08:00:02Z',
        error: null,
      })
      .mockResolvedValue({
        repositoryId: repository.id,
        status: 'queued',
        jobId: 'job-2',
        stage: null,
        progress: 0,
        startedAt: null,
        completedAt: null,
        error: null,
      });
    const start = vi.spyOn(backendService, 'startAnalysis').mockResolvedValue({
      repositoryId: repository.id,
      status: 'queued',
      jobId: 'job-2',
    });
    const hook = renderHook(() => useAnalysisPipeline(repository.id));
    await waitFor(() => expect(hook.result.current.cancelled).toBe(true));

    await act(async () => {
      await hook.result.current.restart();
    });

    expect(start).toHaveBeenCalledWith(repository.id);
    expect(hook.result.current.jobStatus).toBe('queued');
    expect(useAppStore.getState().repositories[0].status).toBe('analysing');
  });

  it('does not restart a cancelled durable job after remount', async () => {
    const start = vi.spyOn(backendService, 'startAnalysis');
    vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
      repositoryId: repository.id,
      status: 'cancelled',
      jobId: 'job-1',
      stage: 'reading-structure',
      progress: 25,
      startedAt: '2026-07-22T08:00:01Z',
      completedAt: '2026-07-22T08:00:02Z',
      error: null,
    });

    const first = renderHook(() => useAnalysisPipeline(repository.id));
    await waitFor(() => expect(first.result.current.cancelled).toBe(true));
    first.unmount();

    const remounted = renderHook(() => useAnalysisPipeline(repository.id));
    await waitFor(() => expect(remounted.result.current.cancelled).toBe(true));

    expect(start).not.toHaveBeenCalled();
  });

  it('retries a failed submission and reaches a terminal state without reloading', async () => {
    const start = vi
      .spyOn(backendService, 'startAnalysis')
      .mockRejectedValueOnce(new Error('start failed before enqueue'))
      .mockResolvedValue({
        repositoryId: repository.id,
        status: 'queued',
        jobId: 'job-1',
      });
    const fetchStatus = vi.spyOn(backendService, 'fetchAnalysisStatus')
      .mockResolvedValueOnce({
        repositoryId: repository.id,
        status: 'queued',
        jobId: null,
        stage: null,
        progress: 0,
        startedAt: null,
        completedAt: null,
        error: null,
      })
      .mockResolvedValueOnce({
        repositoryId: repository.id,
        status: 'queued',
        jobId: null,
        stage: null,
        progress: 0,
        startedAt: null,
        completedAt: null,
        error: null,
      })
      .mockResolvedValue({
        repositoryId: repository.id,
        status: 'completed',
        jobId: 'job-1',
        stage: 'completed',
        progress: 100,
        startedAt: '2026-07-22T08:00:01Z',
        completedAt: '2026-07-22T08:00:02Z',
        error: null,
      });

    const hook = renderHook(() => useAnalysisPipeline(repository.id));
    await waitFor(() => expect(hook.result.current.error).toBe('start failed before enqueue'));
    expect(start).toHaveBeenCalledTimes(1);

    act(() => hook.result.current.retry());

    await waitFor(() => expect(hook.result.current.jobStatus).toBe('completed'));
    expect(start).toHaveBeenCalledTimes(2);
    expect(fetchStatus.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it('submits a newly imported repository only after status confirms no durable job', async () => {
    const start = vi.spyOn(backendService, 'startAnalysis').mockResolvedValue({
      repositoryId: repository.id,
      status: 'queued',
      jobId: 'job-1',
    });
    const fetchStatus = vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
      repositoryId: repository.id,
      status: 'queued',
      jobId: null,
      stage: null,
      progress: 0,
      startedAt: null,
      completedAt: null,
      error: null,
    });

    renderHook(() => useAnalysisPipeline(repository.id));

    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));
    expect(fetchStatus.mock.invocationCallOrder[0]).toBeLessThan(start.mock.invocationCallOrder[0]);
  });

  it.each(['queued', 'running'] as const)(
    'polls an existing %s job without submitting another one',
    async (durableStatus) => {
      const start = vi.spyOn(backendService, 'startAnalysis');
      vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
        repositoryId: repository.id,
        status: durableStatus,
        jobId: 'job-1',
        stage: durableStatus === 'running' ? 'reading-structure' : null,
        progress: durableStatus === 'running' ? 25 : 0,
        startedAt: durableStatus === 'running' ? '2026-07-22T08:00:01Z' : null,
        completedAt: null,
        error: null,
      });

      const hook = renderHook(() => useAnalysisPipeline(repository.id));
      await waitFor(() => expect(hook.result.current.jobStatus).toBe(durableStatus));

      expect(start).not.toHaveBeenCalled();
    },
  );

  it('deduplicates overlapping start requests when the polling effect restarts', async () => {
    let resolveStart: ((response: AnalysisStartResponse) => void) | undefined;
    const pendingStart = new Promise<AnalysisStartResponse>((resolve) => {
      resolveStart = resolve;
    });
    const start = vi.spyOn(backendService, 'startAnalysis').mockReturnValue(pendingStart);
    vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
      repositoryId: repository.id,
      status: 'queued',
      jobId: null,
      stage: null,
      progress: 0,
      startedAt: null,
      completedAt: null,
      error: null,
    });

    const hook = renderHook(() => useAnalysisPipeline(repository.id));
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));

    repositoryState.repositories = [{ ...repository }];
    hook.rerender();
    expect(start).toHaveBeenCalledTimes(1);

    resolveStart?.({
      repositoryId: repository.id,
      status: 'queued',
      jobId: 'job-1',
    });
    await waitFor(() => expect(hook.result.current.jobStatus).toBe('queued'));
    expect(start).toHaveBeenCalledTimes(1);
  });

  describe('getNetworkRetryDelayMs', () => {
    it('backs off exponentially from 1s, capped at 15s', () => {
      expect(getNetworkRetryDelayMs(1)).toBe(1000);
      expect(getNetworkRetryDelayMs(2)).toBe(2000);
      expect(getNetworkRetryDelayMs(3)).toBe(4000);
      expect(getNetworkRetryDelayMs(4)).toBe(8000);
      expect(getNetworkRetryDelayMs(5)).toBe(15000);
    });
  });

  describe('poll resilience', () => {
    const runningResponse = {
      repositoryId: repository.id,
      status: 'running' as const,
      jobId: 'job-1',
      stage: 'reading-structure' as const,
      progress: 25,
      startedAt: '2026-07-22T08:00:01Z',
      completedAt: null,
      error: null,
    };

    it('retries a transient network error with backoff and recovers without ever reporting Analysis Failed', async () => {
      vi.useFakeTimers();
      const fetchStatus = vi
        .spyOn(backendService, 'fetchAnalysisStatus')
        .mockRejectedValueOnce(new NetworkError('/analysis/repo-1/status'))
        .mockResolvedValue(runningResponse);

      const hook = renderHook(() => useAnalysisPipeline(repository.id));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(hook.result.current.connectionStatus).toBe('retrying');
      expect(hook.result.current.error).toBeNull();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });

      expect(hook.result.current.connectionStatus).toBe('connected');
      expect(hook.result.current.jobStatus).toBe('running');
      // A successful poll updates the store, which recreates the polling
      // effect (pre-existing "known limitation" in this hook) -- so recovery
      // may fire one extra immediate poll beyond the failed + retried pair.
      expect(fetchStatus.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    it('stops auto-polling and reports a connectivity error distinct from job failure once retries are exhausted', async () => {
      vi.useFakeTimers();
      vi.spyOn(backendService, 'fetchAnalysisStatus').mockRejectedValue(
        new TimeoutError('/analysis/repo-1/status', 10000),
      );

      const hook = renderHook(() => useAnalysisPipeline(repository.id));

      // Attempt 1 fails immediately; five backoff retries follow: 1s, 2s, 4s, 8s, 15s.
      for (const delay of [0, 1000, 2000, 4000, 8000, 15000]) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(delay);
        });
      }

      expect(hook.result.current.connectionLost).toBe(true);
      expect(hook.result.current.error).toBeNull();
      expect(hook.result.current.status).not.toBe('error');
    });

    it('resumes polling on a manual retry after connectivity is lost', async () => {
      vi.useFakeTimers();
      const fetchStatus = vi
        .spyOn(backendService, 'fetchAnalysisStatus')
        .mockRejectedValue(new NetworkError('/analysis/repo-1/status'));

      const hook = renderHook(() => useAnalysisPipeline(repository.id));
      for (const delay of [0, 1000, 2000, 4000, 8000, 15000]) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(delay);
        });
      }
      expect(hook.result.current.connectionLost).toBe(true);

      fetchStatus.mockReset().mockResolvedValue(runningResponse);
      await act(async () => {
        hook.result.current.retry();
        await vi.advanceTimersByTimeAsync(0);
      });

      expect(hook.result.current.connectionStatus).toBe('connected');
      expect(hook.result.current.jobStatus).toBe('running');
    });

    it('renders a real job failure reported by the API immediately, without retrying', async () => {
      vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
        repositoryId: repository.id,
        status: 'failed',
        jobId: 'job-1',
        stage: 'reading-structure',
        progress: 25,
        startedAt: '2026-07-22T08:00:01Z',
        completedAt: '2026-07-22T08:00:02Z',
        error: 'Extraction crashed.',
      });

      const hook = renderHook(() => useAnalysisPipeline(repository.id));

      await waitFor(() => expect(hook.result.current.jobStatus).toBe('failed'));
      expect(hook.result.current.status).toBe('error');
      expect(hook.result.current.error).toBe('Extraction crashed.');
      expect(hook.result.current.connectionStatus).toBe('connected');
    });
  });
});
