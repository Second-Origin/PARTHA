import { useCallback, useMemo, useState } from 'react';
import type { DataSource, Repository } from '@/shared/types';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepository } from '@/features/repositories/hooks/useRepository';

function isValidGithubUrl(url: string): boolean {
  const pattern = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+(?:\.git)?\/?$/;
  return pattern.test(url.trim());
}

function extractRepoName(url: string): string {
  const parts = url.trim().replace(/\/$/, '').split('/');
  return parts[parts.length - 1]?.replace(/\.git$/i, '') || 'unknown-repo';
}

export function useGitHubImport() {
  const { repositories, selectRepository } = useRepository();
  const addRepository = useAppStore((state) => state.addRepository);
  const [githubUrl, setGithubUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dataSource: DataSource = 'real';

  const repositoryNames = useMemo(
    () => new Set(repositories.map((repo) => repo.name.toLowerCase())),
    [repositories],
  );

  const clearError = useCallback(() => setError(null), []);

  const setUrl = useCallback((url: string) => {
    setGithubUrl(url);
    setError(null);
  }, []);

  const analyseGithub = useCallback(async (): Promise<Repository | null> => {
    setError(null);

    if (!githubUrl.trim()) {
      setError('Please enter a GitHub repository URL.');
      return null;
    }

    if (!isValidGithubUrl(githubUrl)) {
      setError('Invalid GitHub URL. Format: https://github.com/owner/repository');
      return null;
    }

    const repoName = extractRepoName(githubUrl);
    if (repositoryNames.has(repoName.toLowerCase())) {
      setError(`A repository named "${repoName}" already exists.`);
      return null;
    }

    setLoading(true);
    try {
      const importedRepository = await backendService.importFromGithub(githubUrl.trim());

      if (!importedRepository) {
        throw new Error('GitHub import did not return a repository.');
      }

      await backendService.startAnalysis(importedRepository.id);
      const repository = await backendService.fetchRepository(importedRepository.id);

      if (!repository) {
        throw new Error('Repository was imported but could not be refreshed from the backend.');
      }

      addRepository(repository);
      selectRepository(repository);
      setGithubUrl('');
      return repository;
    } catch (caught) {
      setError(getErrorMessage(caught));
      return null;
    } finally {
      setLoading(false);
    }
  }, [addRepository, githubUrl, repositoryNames, selectRepository]);

  return {
    githubUrl,
    setGithubUrl: setUrl,
    loading,
    error,
    empty: githubUrl.trim().length === 0,
    success: isValidGithubUrl(githubUrl),
    source: dataSource,
    previewName: isValidGithubUrl(githubUrl) ? extractRepoName(githubUrl) : null,
    analyseGithub,
    retry: clearError,
    refresh: clearError,
  };
}
