import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { reviewService } from './review';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('reviewService', () => {
  it('getReview with no query builds the bare endpoint and defaults missing categories and findings honestly', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    const result = await reviewService.getReview('repo-1');

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/review', undefined);
    expect(result.categories).toEqual([]);
    expect(result.findings).toEqual([]);
  });

  it('preserves categories and findings the backend actually sent instead of overwriting them', async () => {
    const categories = [{ id: 'architecture_boundaries', label: 'Architecture', state: 'assessed', explanation: '', findingCount: 1 }];
    const findings = [{ id: 'finding-1' }];
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1', categories, findings });

    const result = await reviewService.getReview('repo-1');

    expect(result.categories).toEqual(categories);
    expect(result.findings).toEqual(findings);
  });

  it('encodes offset and limit into the query string', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    await reviewService.getReview('repo-1', { offset: 50, limit: 25 });

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/review?offset=50&limit=25', undefined);
  });

  it('encodes category, severity, and diagnosticCode filters into the query string', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    await reviewService.getReview('repo-1', {
      category: 'relationship_resolution',
      severity: 'critical',
      diagnosticCode: 'RI-RES-UNRESOLVED',
    });

    expect(api.get).toHaveBeenCalledWith(
      '/analysis/repo-1/review?category=relationship_resolution&severity=critical&diagnosticCode=RI-RES-UNRESOLVED',
      undefined,
    );
  });

  it('omits an empty-string filter rather than sending a meaningless query param', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    await reviewService.getReview('repo-1', { category: '', offset: 0 });

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/review?offset=0', undefined);
  });

  it('forwards the request config alongside a query', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });
    const controller = new AbortController();

    await reviewService.getReview('repo-1', { limit: 10 }, { signal: controller.signal });

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/review?limit=10', { signal: controller.signal });
  });

  it('propagates a rejected request rather than swallowing it (e.g. no sealed snapshot yet)', async () => {
    const error = new Error('not found');
    vi.mocked(api.get).mockRejectedValue(error);

    await expect(reviewService.getReview('repo-1')).rejects.toBe(error);
  });
});
