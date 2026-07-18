import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { backendService } from '@/shared/services/backend';
import { ApiError } from '@/shared/services/api';
import type { Repository } from '@/shared/types';
import { useGitHubImport } from './useGitHubImport';

const repositoryState = vi.hoisted(() => ({
  repositories: [] as Repository[],
  selectRepository: vi.fn(),
}));

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({
    repositories: repositoryState.repositories,
    selectRepository: repositoryState.selectRepository,
  }),
}));

function repository(id: string, name: string): Repository {
  return {
    id,
    name,
    source: 'github',
    sourceUrl: `https://github.com/example/${name}`,
    size: 0,
    fileCount: 0,
    status: 'analysing',
    dataSource: 'real',
    analysisStage: 'uploading',
    analysisProgress: 0,
    uploadedAt: '2026-01-01T00:00:00Z',
    meta: null,
    fileTree: [],
  };
}

function mockBackendLifecycle() {
  return {
    importFromGithub: vi.spyOn(backendService, 'importFromGithub').mockResolvedValue(null),
    startAnalysis: vi.spyOn(backendService, 'startAnalysis').mockResolvedValue(null),
    fetchRepository: vi.spyOn(backendService, 'fetchRepository').mockResolvedValue(null),
  };
}

describe('useGitHubImport', () => {
  beforeEach(() => {
    repositoryState.repositories = [];
    repositoryState.selectRepository.mockReset();
    useAppStore.setState({ repositories: [], activeRepositoryId: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each(['', '   '])('rejects an empty or whitespace-only URL without calling the backend: %j', async (url) => {
    const backend = mockBackendLifecycle();
    const hook = renderHook(() => useGitHubImport());

    act(() => {
      hook.result.current.setGithubUrl(url);
    });

    let imported: Repository | null = null;
    await act(async () => {
      imported = await hook.result.current.analyseGithub();
    });

    expect(imported).toBeNull();
    expect(hook.result.current.error).toBe('Please enter a GitHub repository URL.');
    expect(backend.importFromGithub).not.toHaveBeenCalled();
    expect(backend.startAnalysis).not.toHaveBeenCalled();
    expect(backend.fetchRepository).not.toHaveBeenCalled();
  });

  it.each([
    'http://github.com/example/project',
    'https://gitlab.com/example/project',
    'https://github.com/example',
    'https://github.com/example/project/tree/main',
  ])('rejects malformed or non-GitHub URLs without calling the backend: %s', async (url) => {
    const backend = mockBackendLifecycle();
    const hook = renderHook(() => useGitHubImport());

    act(() => {
      hook.result.current.setGithubUrl(url);
    });

    let imported: Repository | null = null;
    await act(async () => {
      imported = await hook.result.current.analyseGithub();
    });

    expect(imported).toBeNull();
    expect(hook.result.current.error).toBe(
      'Invalid GitHub URL. Format: https://github.com/owner/repository',
    );
    expect(backend.importFromGithub).not.toHaveBeenCalled();
    expect(backend.startAnalysis).not.toHaveBeenCalled();
    expect(backend.fetchRepository).not.toHaveBeenCalled();
  });

  it('rejects a duplicate repository name case-insensitively without calling the backend', async () => {
    repositoryState.repositories = [repository('existing-id', 'Existing-Project')];
    const backend = mockBackendLifecycle();
    const hook = renderHook(() => useGitHubImport());

    act(() => {
      hook.result.current.setGithubUrl('https://github.com/example/existing-project.git');
    });

    let imported: Repository | null = null;
    await act(async () => {
      imported = await hook.result.current.analyseGithub();
    });

    expect(imported).toBeNull();
    expect(hook.result.current.error).toBe('A repository named "existing-project" already exists.');
    expect(backend.importFromGithub).not.toHaveBeenCalled();
    expect(backend.startAnalysis).not.toHaveBeenCalled();
    expect(backend.fetchRepository).not.toHaveBeenCalled();
  });

  it.each([
    ['https://github.com/example/project', 'project'],
    ['https://github.com/example/project.git', 'project'],
  ])('imports a valid GitHub URL and preserves its repository name: %s', async (url, name) => {
    const importedRepository = repository('imported-id', name);
    const refreshedRepository = repository('refreshed-id', name);
    const backend = mockBackendLifecycle();
    backend.importFromGithub.mockResolvedValue(importedRepository);
    backend.fetchRepository.mockResolvedValue(refreshedRepository);
    const hook = renderHook(() => useGitHubImport());

    act(() => {
      hook.result.current.setGithubUrl(` ${url} `);
    });

    expect(hook.result.current.success).toBe(true);
    expect(hook.result.current.previewName).toBe(name);

    let imported: Repository | null = null;
    await act(async () => {
      imported = await hook.result.current.analyseGithub();
    });

    expect(backend.importFromGithub).toHaveBeenCalledOnce();
    expect(backend.importFromGithub).toHaveBeenCalledWith(url);
    expect(backend.startAnalysis).toHaveBeenCalledOnce();
    expect(backend.startAnalysis).toHaveBeenCalledWith(importedRepository.id);
    expect(backend.fetchRepository).toHaveBeenCalledOnce();
    expect(backend.fetchRepository).toHaveBeenCalledWith(importedRepository.id);
    expect(backend.importFromGithub.mock.invocationCallOrder[0]).toBeLessThan(
      backend.startAnalysis.mock.invocationCallOrder[0],
    );
    expect(backend.startAnalysis.mock.invocationCallOrder[0]).toBeLessThan(
      backend.fetchRepository.mock.invocationCallOrder[0],
    );
    expect(imported).toEqual(refreshedRepository);
    expect(useAppStore.getState().repositories).toEqual([refreshedRepository]);
    expect(repositoryState.selectRepository).toHaveBeenCalledWith(refreshedRepository);
    expect(hook.result.current.githubUrl).toBe('');
    expect(hook.result.current.loading).toBe(false);
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.empty).toBe(true);
  });

  it('reports an import that returns no repository', async () => {
    const backend = mockBackendLifecycle();
    const hook = renderHook(() => useGitHubImport());

    act(() => {
      hook.result.current.setGithubUrl('https://github.com/example/project');
    });

    let imported: Repository | null = null;
    await act(async () => {
      imported = await hook.result.current.analyseGithub();
    });

    expect(imported).toBeNull();
    expect(hook.result.current.error).toBe('GitHub import did not return a repository.');
    expect(hook.result.current.loading).toBe(false);
    expect(backend.importFromGithub).toHaveBeenCalledOnce();
    expect(backend.startAnalysis).not.toHaveBeenCalled();
    expect(backend.fetchRepository).not.toHaveBeenCalled();
  });

  it('reports an import that cannot be refreshed after analysis starts', async () => {
    const importedRepository = repository('imported-id', 'project');
    const backend = mockBackendLifecycle();
    backend.importFromGithub.mockResolvedValue(importedRepository);
    const hook = renderHook(() => useGitHubImport());

    act(() => {
      hook.result.current.setGithubUrl('https://github.com/example/project');
    });

    let imported: Repository | null = null;
    await act(async () => {
      imported = await hook.result.current.analyseGithub();
    });

    expect(imported).toBeNull();
    expect(hook.result.current.error).toBe(
      'Repository was imported but could not be refreshed from the backend.',
    );
    expect(hook.result.current.loading).toBe(false);
    expect(backend.importFromGithub).toHaveBeenCalledOnce();
    expect(backend.startAnalysis).toHaveBeenCalledOnce();
    expect(backend.fetchRepository).toHaveBeenCalledOnce();
  });

  it('reports a backend rejection through getErrorMessage', async () => {
    const importedRepository = repository('imported-id', 'project');
    const backend = mockBackendLifecycle();
    backend.importFromGithub.mockResolvedValue(importedRepository);
    backend.startAnalysis.mockRejectedValue(
      new ApiError(503, 'Service Unavailable', null, '/repositories/imported-id/analysis'),
    );
    const hook = renderHook(() => useGitHubImport());

    act(() => {
      hook.result.current.setGithubUrl('https://github.com/example/project');
    });

    let imported: Repository | null = null;
    await act(async () => {
      imported = await hook.result.current.analyseGithub();
    });

    expect(imported).toBeNull();
    expect(hook.result.current.error).toBe('Service is temporarily unavailable. Please try again.');
    expect(hook.result.current.loading).toBe(false);
    expect(backend.importFromGithub).toHaveBeenCalledOnce();
    expect(backend.startAnalysis).toHaveBeenCalledOnce();
    expect(backend.fetchRepository).not.toHaveBeenCalled();
  });
});
