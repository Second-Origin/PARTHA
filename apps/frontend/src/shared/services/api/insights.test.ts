import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { insightsService } from './insights';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('insightsService', () => {
  it('getInsights resolves the insights endpoint and defaults every missing collection honestly', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    const result = await insightsService.getInsights('repo-1');

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/insights', undefined);
    expect(result.extractorSet).toEqual([]);
    expect(result.metrics).toEqual([]);
    expect(result.relationshipsByPredicate).toEqual([]);
    expect(result.diagnosticsBySeverity).toEqual([]);
    expect(result.diagnosticsByCode).toEqual([]);
    expect(result.languages).toEqual([]);
    expect(result.changeOverTime).toEqual({
      assessmentState: 'not_assessed',
      message: 'Change-over-time insights are not available yet.',
    });
  });

  it('preserves values the backend actually sent instead of overwriting them', async () => {
    const changeOverTime = { assessmentState: 'assessed' as const, message: 'trending up' };
    vi.mocked(api.get).mockResolvedValue({
      repositoryId: 'repo-1',
      extractorSet: [{ name: 'typescript-extractor', version: '1.0.0', evidenceRecordCount: 3 }],
      changeOverTime,
    });

    const result = await insightsService.getInsights('repo-1');

    expect(result.extractorSet).toEqual([{ name: 'typescript-extractor', version: '1.0.0', evidenceRecordCount: 3 }]);
    expect(result.changeOverTime).toBe(changeOverTime);
  });

  it('propagates a rejected request rather than swallowing it', async () => {
    const error = new Error('not found');
    vi.mocked(api.get).mockRejectedValue(error);

    await expect(insightsService.getInsights('repo-1')).rejects.toBe(error);
  });
});
