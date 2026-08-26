import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { dependencyService } from './dependencies';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('dependencyService', () => {
  it('getDependencyGraph resolves the dependencies endpoint and defaults a missing diagnostics array', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    const result = await dependencyService.getDependencyGraph('repo-1');

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/dependencies', undefined);
    expect(result.diagnostics).toEqual([]);
  });

  it('preserves diagnostics the backend actually sent instead of overwriting them', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1', diagnostics: [{ code: 'D1' }] });

    const result = await dependencyService.getDependencyGraph('repo-1');

    expect(result.diagnostics).toEqual([{ code: 'D1' }]);
  });

  it('propagates a rejected request rather than swallowing it', async () => {
    const error = new Error('not found');
    vi.mocked(api.get).mockRejectedValue(error);

    await expect(dependencyService.getDependencyGraph('repo-1')).rejects.toBe(error);
  });
});
