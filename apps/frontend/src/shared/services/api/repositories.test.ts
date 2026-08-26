import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { repositoryService, repositoryIntelligenceService } from './repositories';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('repositoryService', () => {
  it('list gets /repositories', async () => {
    const response = { data: [], meta: { total: 0 } };
    vi.mocked(api.get).mockResolvedValue(response);

    const result = await repositoryService.list();

    expect(api.get).toHaveBeenCalledWith('/repositories', undefined);
    expect(result).toBe(response);
  });

  it('getById gets /repositories/{id}', async () => {
    const repository = { id: 'repo-1' };
    vi.mocked(api.get).mockResolvedValue(repository);

    const result = await repositoryService.getById('repo-1');

    expect(api.get).toHaveBeenCalledWith('/repositories/repo-1', undefined);
    expect(result).toBe(repository);
  });

  it('getFile gets /repositories/{id}/file with an encoded path', async () => {
    vi.mocked(api.get).mockResolvedValue({ path: 'src/a b.ts', content: '' });

    await repositoryService.getFile('repo-1', 'src/a b.ts');

    expect(api.get).toHaveBeenCalledWith('/repositories/repo-1/file?path=src%2Fa%20b.ts', undefined);
  });

  it('delete sends a DELETE to /repositories/{id} with no body', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined);

    await repositoryService.delete('repo-1');

    expect(api.delete).toHaveBeenCalledWith('/repositories/repo-1', undefined, undefined);
  });

  it('importFromGithub posts the request body to /repositories/github', async () => {
    const request = { url: 'https://github.com/example/repo' };
    const response = { id: 'repo-2' };
    vi.mocked(api.post).mockResolvedValue(response);

    const result = await repositoryService.importFromGithub(request as never);

    expect(api.post).toHaveBeenCalledWith('/repositories/github', request, undefined);
    expect(result).toBe(response);
  });

  it('propagates a rejected request rather than swallowing it', async () => {
    const error = new Error('not found');
    vi.mocked(api.get).mockRejectedValue(error);

    await expect(repositoryService.getById('missing')).rejects.toBe(error);
  });
});

describe('repositoryIntelligenceService', () => {
  it('getSnapshot gets the encoded snapshot endpoint', async () => {
    const snapshot = { snapshotId: 'snap one' };
    vi.mocked(api.get).mockResolvedValue(snapshot);

    const result = await repositoryIntelligenceService.getSnapshot('snap one');

    expect(api.get).toHaveBeenCalledWith('/intelligence/v1/snapshots/snap%20one', undefined);
    expect(result).toBe(snapshot);
  });

  it('listSymbols defaults offset and limit and encodes the snapshot id', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [], pagination: { offset: 0, limit: 50, total: 0 } });

    await repositoryIntelligenceService.listSymbols('snap one');

    expect(api.get).toHaveBeenCalledWith('/intelligence/v1/snapshots/snap%20one/symbols?offset=0&limit=50', undefined);
  });

  it('listSymbols honours an explicit offset and limit', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [], pagination: { offset: 50, limit: 25, total: 0 } });

    await repositoryIntelligenceService.listSymbols('snap-1', 50, 25);

    expect(api.get).toHaveBeenCalledWith('/intelligence/v1/snapshots/snap-1/symbols?offset=50&limit=25', undefined);
  });

  it('listNeighbours encodes both the snapshot id and the node key', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [], pagination: { offset: 0, limit: 50, total: 0 } });

    await repositoryIntelligenceService.listNeighbours('snap-1', 'node/one two');

    expect(api.get).toHaveBeenCalledWith(
      '/intelligence/v1/snapshots/snap-1/neighbours?nodeKey=node%2Fone%20two&offset=0&limit=50',
      undefined,
    );
  });

  it('listReferences defaults offset and limit', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [], pagination: { offset: 0, limit: 50, total: 0 } });

    await repositoryIntelligenceService.listReferences('snap-1');

    expect(api.get).toHaveBeenCalledWith('/intelligence/v1/snapshots/snap-1/references?offset=0&limit=50', undefined);
  });

  it('listAssertions defaults offset and limit', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [], pagination: { offset: 0, limit: 50, total: 0 } });

    await repositoryIntelligenceService.listAssertions('snap-1');

    expect(api.get).toHaveBeenCalledWith('/intelligence/v1/snapshots/snap-1/assertions?offset=0&limit=50', undefined);
  });

  it('listPaths defaults offset and limit', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [], pagination: { offset: 0, limit: 50, total: 0 } });

    await repositoryIntelligenceService.listPaths('snap-1');

    expect(api.get).toHaveBeenCalledWith('/intelligence/v1/snapshots/snap-1/paths?offset=0&limit=50', undefined);
  });

  it('listEvidence defaults offset and limit', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [], pagination: { offset: 0, limit: 50, total: 0 } });

    await repositoryIntelligenceService.listEvidence('snap-1');

    expect(api.get).toHaveBeenCalledWith('/intelligence/v1/snapshots/snap-1/evidence?offset=0&limit=50', undefined);
  });

  it('propagates a rejected request rather than swallowing it', async () => {
    const error = new Error('not found');
    vi.mocked(api.get).mockRejectedValue(error);

    await expect(repositoryIntelligenceService.getSnapshot('missing')).rejects.toBe(error);
  });
});
