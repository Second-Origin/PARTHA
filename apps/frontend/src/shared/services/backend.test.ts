import { describe, expect, it, vi } from 'vitest';
import { backendService } from './backend';
import { repositoryService } from './api/repositories';
import { uploadService } from './api/upload';
import { analysisService } from './api/analysis';
import { architectureService } from './api/architecture';
import { reviewService } from './api/review';
import { dependencyService } from './api/dependencies';
import { insightsService } from './api/insights';
import type { RepositoryResponse } from './api/types';

vi.mock('./api/repositories', () => ({
  repositoryService: { list: vi.fn(), getById: vi.fn(), delete: vi.fn(), importFromGithub: vi.fn() },
}));
vi.mock('./api/upload', () => ({ uploadService: { uploadRepository: vi.fn() } }));
vi.mock('./api/analysis', () => ({
  analysisService: { start: vi.fn(), getStatus: vi.fn(), cancel: vi.fn() },
}));
vi.mock('./api/architecture', () => ({
  architectureService: { getArchitecture: vi.fn(), getAuthenticationExplanation: vi.fn() },
}));
vi.mock('./api/review', () => ({ reviewService: { getReview: vi.fn() } }));
vi.mock('./api/dependencies', () => ({ dependencyService: { getDependencyGraph: vi.fn() } }));
vi.mock('./api/insights', () => ({ insightsService: { getInsights: vi.fn() } }));

function repositoryResponse(overrides: Partial<RepositoryResponse> = {}): RepositoryResponse {
  return {
    id: 'repo-1',
    name: 'sample',
    description: null,
    source: 'upload',
    sourceUrl: null,
    size: 10,
    fileCount: 5,
    status: 'completed',
    analysisStage: null,
    analysisProgress: 100,
    uploadedAt: '2026-07-25T00:00:00Z',
    analysedAt: null,
    errorMessage: null,
    revision: null,
    commitSha: null,
    meta: null,
    ...overrides,
  } as RepositoryResponse;
}

describe('backendService repository mapping (mapRepositoryResponse)', () => {
  it('turns falsy optional fields into undefined rather than leaking empty strings', async () => {
    vi.mocked(repositoryService.getById).mockResolvedValue(
      repositoryResponse({ description: '', sourceUrl: '', analysedAt: '', errorMessage: '' }),
    );

    const repository = await backendService.fetchRepository('repo-1');

    expect(repository?.description).toBeUndefined();
    expect(repository?.sourceUrl).toBeUndefined();
    expect(repository?.analysedAt).toBeUndefined();
    expect(repository?.errorMessage).toBeUndefined();
  });

  it('preserves a real description, sourceUrl, analysedAt, and errorMessage when present', async () => {
    vi.mocked(repositoryService.getById).mockResolvedValue(
      repositoryResponse({
        description: 'A sample repo',
        sourceUrl: 'https://github.com/example/repo',
        analysedAt: '2026-07-25T01:00:00Z',
        errorMessage: 'boom',
      }),
    );

    const repository = await backendService.fetchRepository('repo-1');

    expect(repository?.description).toBe('A sample repo');
    expect(repository?.sourceUrl).toBe('https://github.com/example/repo');
    expect(repository?.analysedAt).toBe('2026-07-25T01:00:00Z');
    expect(repository?.errorMessage).toBe('boom');
  });

  it('defaults a null revision to null and normalises a missing ref to null', async () => {
    vi.mocked(repositoryService.getById).mockResolvedValue(
      repositoryResponse({ revision: { kind: 'upload', value: 'sha256:abc' } as never }),
    );

    const repository = await backendService.fetchRepository('repo-1');

    expect(repository?.revision).toEqual({ kind: 'upload', value: 'sha256:abc', ref: null });
  });

  it('defaults a null meta and fileTree honestly rather than fabricating placeholder content', async () => {
    vi.mocked(repositoryService.getById).mockResolvedValue(repositoryResponse({ meta: null, fileTree: undefined }));

    const repository = await backendService.fetchRepository('repo-1');

    expect(repository?.meta).toBeNull();
    expect(repository?.fileTree).toEqual([]);
  });

  it('fetchRepositories maps every entry in the list response', async () => {
    vi.mocked(repositoryService.list).mockResolvedValue({
      data: [repositoryResponse({ id: 'repo-1' }), repositoryResponse({ id: 'repo-2' })],
      total: 2,
    });

    const repositories = await backendService.fetchRepositories();

    expect(repositories.map((r) => r.id)).toEqual(['repo-1', 'repo-2']);
  });
});

describe('backendService delegation to the api/* service layer', () => {
  it('uploadRepository forwards the progress callback and maps the response', async () => {
    vi.mocked(uploadService.uploadRepository).mockResolvedValue(repositoryResponse({ id: 'repo-3' }));
    const onProgress = vi.fn();
    const file = new File(['x'], 'repo.zip');

    const repository = await backendService.uploadRepository(file, { name: 'repo' }, onProgress);

    expect(uploadService.uploadRepository).toHaveBeenCalledWith(file, { name: 'repo' }, { onUploadProgress: onProgress });
    expect(repository?.id).toBe('repo-3');
  });

  it('importFromGithub forwards the url and branch and maps the response', async () => {
    vi.mocked(repositoryService.importFromGithub).mockResolvedValue(repositoryResponse({ id: 'repo-4' }));

    const repository = await backendService.importFromGithub('https://github.com/example/repo', 'main');

    expect(repositoryService.importFromGithub).toHaveBeenCalledWith({
      url: 'https://github.com/example/repo',
      branch: 'main',
    });
    expect(repository?.id).toBe('repo-4');
  });

  it('startAnalysis, fetchAnalysisStatus, and cancelAnalysis delegate to analysisService', async () => {
    vi.mocked(analysisService.start).mockResolvedValue({ repositoryId: 'repo-1', status: 'queued', jobId: 'job-1' });
    vi.mocked(analysisService.getStatus).mockResolvedValue({ repositoryId: 'repo-1', status: 'analysing' } as never);
    vi.mocked(analysisService.cancel).mockResolvedValue({ repositoryId: 'repo-1', status: 'cancelled' } as never);

    await backendService.startAnalysis('repo-1');
    await backendService.fetchAnalysisStatus('repo-1');
    await backendService.cancelAnalysis('repo-1');

    expect(analysisService.start).toHaveBeenCalledWith('repo-1');
    expect(analysisService.getStatus).toHaveBeenCalledWith('repo-1');
    expect(analysisService.cancel).toHaveBeenCalledWith('repo-1');
  });

  it('fetchArchitecture, fetchAuthenticationExplanation, fetchReview, fetchInsights, and fetchDependencyGraph delegate by repository id', async () => {
    const repository = (await (async () => {
      vi.mocked(repositoryService.getById).mockResolvedValue(repositoryResponse({ id: 'repo-5' }));
      return backendService.fetchRepository('repo-5');
    })())!;

    vi.mocked(architectureService.getArchitecture).mockResolvedValue({ repositoryId: 'repo-5' } as never);
    vi.mocked(architectureService.getAuthenticationExplanation).mockResolvedValue({ repositoryId: 'repo-5' } as never);
    vi.mocked(reviewService.getReview).mockResolvedValue({ repositoryId: 'repo-5' } as never);
    vi.mocked(insightsService.getInsights).mockResolvedValue({ repositoryId: 'repo-5' } as never);
    vi.mocked(dependencyService.getDependencyGraph).mockResolvedValue({ repositoryId: 'repo-5' } as never);

    await backendService.fetchArchitecture(repository);
    await backendService.fetchAuthenticationExplanation(repository);
    await backendService.fetchReview(repository);
    await backendService.fetchInsights(repository);
    await backendService.fetchDependencyGraph(repository.id);

    expect(architectureService.getArchitecture).toHaveBeenCalledWith('repo-5');
    expect(architectureService.getAuthenticationExplanation).toHaveBeenCalledWith('repo-5');
    expect(reviewService.getReview).toHaveBeenCalledWith('repo-5', undefined);
    expect(insightsService.getInsights).toHaveBeenCalledWith('repo-5');
    expect(dependencyService.getDependencyGraph).toHaveBeenCalledWith('repo-5');
  });

  it('deleteRepository calls delete and resolves true on success', async () => {
    vi.mocked(repositoryService.delete).mockResolvedValue(undefined);

    const result = await backendService.deleteRepository('repo-1');

    expect(repositoryService.delete).toHaveBeenCalledWith('repo-1');
    expect(result).toBe(true);
  });

  it('propagates a rejected fetchReview instead of swallowing it (e.g. no sealed snapshot yet)', async () => {
    const error = new Error('not found');
    vi.mocked(reviewService.getReview).mockRejectedValue(error);
    vi.mocked(repositoryService.getById).mockResolvedValue(repositoryResponse({ id: 'repo-6' }));
    const repository = (await backendService.fetchRepository('repo-6'))!;

    await expect(backendService.fetchReview(repository)).rejects.toBe(error);
  });
});
