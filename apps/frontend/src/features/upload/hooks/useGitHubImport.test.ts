import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { backendService } from '@/shared/services/backend';
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
    const importSpy = vi.spyOn(backendService, 'importFromGithub');
    const analysisSpy = vi.spyOn(backendService, 'startAnalysis');
    const refreshSpy = vi.spyOn(backendService, 'fetchRepository');
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
    expect(importSpy).not.toHaveBeenCalled();
    expect(analysisSpy).not.toHaveBeenCalled();
    expect(refreshSpy).not.toHaveBeenCalled();
  });

  it.each([
    'http://github.com/example/project',
    'https://gitlab.com/example/project',
    'https://github.com/example',
    'https://github.com/example/project/tree/main',
  ])('rejects malformed or non-GitHub URLs without calling the backend: %s', async (url) => {
    const importSpy = vi.spyOn(backendService, 'importFromGithub');
    const analysisSpy = vi.spyOn(backendService, 'startAnalysis');
    const refreshSpy = vi.spyOn(backendService, 'fetchRepository');
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
    expect(importSpy).not.toHaveBeenCalled();
    expect(analysisSpy).not.toHaveBeenCalled();
    expect(refreshSpy).not.toHaveBeenCalled();
  });

  it('rejects a duplicate repository name case-insensitively without calling the backend', async () => {
    repositoryState.repositories = [repository('existing-id', 'Existing-Project')];
    const importSpy = vi.spyOn(backendService, 'importFromGithub');
    const analysisSpy = vi.spyOn(backendService, 'startAnalysis');
    const refreshSpy = vi.spyOn(backendService, 'fetchRepository');
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
    expect(importSpy).not.toHaveBeenCalled();
    expect(analysisSpy).not.toHaveBeenCalled();
    expect(refreshSpy).not.toHaveBeenCalled();
  });

  it.each([
    ['https://github.com/example/project', 'project'],
    ['https://github.com/example/project.git', 'project'],
  ])('imports a valid GitHub URL and preserves its repository name: %s', async (url, name) => {
    const importedRepository = repository('imported-id', name);
    const refreshedRepository = repository('refreshed-id', name);
    const importSpy = vi.spyOn(backendService, 'importFromGithub').mockResolvedValue(importedRepository);
    const analysisSpy = vi.spyOn(backendService, 'startAnalysis').mockResolvedValue(null);
    const refreshSpy = vi.spyOn(backendService, 'fetchRepository').mockResolvedValue(refreshedRepository);
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

    expect(importSpy).toHaveBeenCalledOnce();
    expect(importSpy).toHaveBeenCalledWith(url);
    expect(analysisSpy).toHaveBeenCalledOnce();
    expect(analysisSpy).toHaveBeenCalledWith(importedRepository.id);
    expect(refreshSpy).toHaveBeenCalledOnce();
    expect(refreshSpy).toHaveBeenCalledWith(importedRepository.id);
    expect(importSpy.mock.invocationCallOrder[0]).toBeLessThan(analysisSpy.mock.invocationCallOrder[0]);
    expect(analysisSpy.mock.invocationCallOrder[0]).toBeLessThan(refreshSpy.mock.invocationCallOrder[0]);
    expect(imported).toEqual(refreshedRepository);
    expect(useAppStore.getState().repositories).toEqual([refreshedRepository]);
    expect(repositoryState.selectRepository).toHaveBeenCalledWith(refreshedRepository);
    expect(hook.result.current.githubUrl).toBe('');
    expect(hook.result.current.loading).toBe(false);
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.empty).toBe(true);
  });
});
