import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { architectureService } from './architecture';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('architectureService', () => {
  it('getArchitecture resolves the architecture endpoint and defaults a missing diagnostics array', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    const result = await architectureService.getArchitecture('repo-1');

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/architecture', undefined);
    expect(result.diagnostics).toEqual([]);
  });

  it('getArchitecture preserves diagnostics the backend actually sent', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1', diagnostics: [{ code: 'X' }] });

    const result = await architectureService.getArchitecture('repo-1');

    expect(result.diagnostics).toEqual([{ code: 'X' }]);
  });

  it('getAuthenticationExplanation resolves its endpoint and defaults every missing collection', async () => {
    vi.mocked(api.get).mockResolvedValue({ repositoryId: 'repo-1' });

    const result = await architectureService.getAuthenticationExplanation('repo-1');

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/architecture/authentication', undefined);
    expect(result.claims).toEqual([]);
    expect(result.relationships).toEqual([]);
    expect(result.chains).toEqual([]);
    expect(result.diagnostics).toEqual([]);
  });

  it('getRevisionManifest resolves the revision-manifest endpoint', async () => {
    const manifest = { manifest: { snapshotId: 'snap-1' } };
    vi.mocked(api.get).mockResolvedValue(manifest);

    const result = await architectureService.getRevisionManifest('repo-1');

    expect(api.get).toHaveBeenCalledWith('/analysis/repo-1/revision-manifest', undefined);
    expect(result).toBe(manifest);
  });

  it('getEvidenceSource builds an exact query string from every parameter', async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 'ready' });

    await architectureService.getEvidenceSource('repo-1', 'snap-1', 'fact-1', 'src/a b.ts', 10, 20);

    const expectedQuery = new URLSearchParams({
      snapshotId: 'snap-1',
      factId: 'fact-1',
      path: 'src/a b.ts',
      startLine: '10',
      endLine: '20',
    }).toString();
    expect(api.get).toHaveBeenCalledWith(`/analysis/repo-1/evidence?${expectedQuery}`, undefined);
  });

  it('propagates a rejected evidence-source request', async () => {
    const error = new Error('not found');
    vi.mocked(api.get).mockRejectedValue(error);

    await expect(
      architectureService.getEvidenceSource('repo-1', 'snap-1', 'fact-1', 'src/a.ts', 1, 2),
    ).rejects.toBe(error);
  });
});
