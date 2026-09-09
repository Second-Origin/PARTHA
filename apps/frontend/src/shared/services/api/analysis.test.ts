import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { analysisService } from './analysis';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('analysisService', () => {
  it('getStatus resolves the status endpoint for the repository', async () => {
    const status = { repositoryId: 'repo-1', status: 'analysing' };
    vi.mocked(api.get).mockResolvedValue(status);

    const result = await analysisService.getStatus('repo-1');

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/status', undefined);
    expect(result).toBe(status);
  });

  it('start posts to the start endpoint with no body', async () => {
    const started = { repositoryId: 'repo-1', status: 'queued', jobId: 'job-1' };
    vi.mocked(api.post).mockResolvedValue(started);

    const result = await analysisService.start('repo-1');

    expect(api.post).toHaveBeenCalledWith('/analysis/repo-1/start', undefined, undefined);
    expect(result).toBe(started);
  });

  it('cancel posts to the cancel endpoint with no body', async () => {
    const cancelled = { repositoryId: 'repo-1', status: 'cancelled' };
    vi.mocked(api.post).mockResolvedValue(cancelled);

    const result = await analysisService.cancel('repo-1');

    expect(api.post).toHaveBeenCalledWith('/analysis/repo-1/cancel', undefined, undefined);
    expect(result).toBe(cancelled);
  });

  it('propagates a rejected request rather than swallowing it', async () => {
    const error = new Error('network down');
    vi.mocked(api.get).mockRejectedValue(error);

    await expect(analysisService.getStatus('repo-1')).rejects.toBe(error);
  });

  it('forwards the request config (e.g. an abort signal) through to the client', async () => {
    vi.mocked(api.get).mockResolvedValue({});
    const controller = new AbortController();

    await analysisService.getStatus('repo-1', { signal: controller.signal });

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/status', { signal: controller.signal });
  });
});
