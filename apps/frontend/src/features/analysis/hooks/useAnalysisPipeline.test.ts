import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { backendService } from '@/shared/services/backend';
import type { AnalysisStartResponse } from '@/shared/services/api/types';
import type { Repository } from '@/shared/types';
import { useAnalysisPipeline } from './useAnalysisPipeline';

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
  });

  it('requests server cancellation and stops in the cancelled terminal state', async () => {
    vi.spyOn(backendService, 'startAnalysis').mockResolvedValue({
      repositoryId: repository.id,
      status: 'queued',
      jobId: 'job-1',
    });
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
        jobId: 'job-1',
        stage: null,
        progress: 0,
        startedAt: null,
        completedAt: null,
        error: null,
      })
      .mockResolvedValueOnce({
        repositoryId: repository.id,
        status: 'running',
        jobId: 'job-1',
        stage: 'reading-structure',
        progress: 25,
        startedAt: '2026-07-22T08:00:01Z',
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

  it('resubmits when queued status has no durable job id', async () => {
    const start = vi
      .spyOn(backendService, 'startAnalysis')
      .mockResolvedValueOnce({
        repositoryId: repository.id,
        status: 'queued',
        jobId: null,
      })
      .mockResolvedValue({
        repositoryId: repository.id,
        status: 'queued',
        jobId: 'job-1',
      });
    vi.spyOn(backendService, 'fetchAnalysisStatus')
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

    await waitFor(() => expect(hook.result.current.jobStatus).toBe('completed'));
    expect(start).toHaveBeenCalledTimes(2);
  });

  it('deduplicates overlapping start requests when the polling effect restarts', async () => {
    let resolveStart: ((response: AnalysisStartResponse) => void) | undefined;
    const pendingStart = new Promise<AnalysisStartResponse>((resolve) => {
      resolveStart = resolve;
    });
    const start = vi.spyOn(backendService, 'startAnalysis').mockReturnValue(pendingStart);
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
    await waitFor(() => expect(hook.result.current.jobStatus).toBe('running'));
    expect(start).toHaveBeenCalledTimes(1);
  });
});
