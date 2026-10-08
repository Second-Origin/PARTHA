import { useCallback, useState } from 'react';
import type { Repository } from '@/shared/types';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepository } from '@/features/repositories/hooks/useRepository';

// A URL copied from a branch page ends in /tree/<branch>; the backend splits
// that off as the ref, so it is accepted here too. Any other extra path
// (issues, blob, ...) is still refused.
const GITHUB_URL =
  /^https:\/\/(?:www\.)?github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+?)(?:\.git)?(?:\/tree\/[^\s?#]+)?\/?(?:[?#]\S*)?$/;

function isValidGithubUrl(url: string): boolean {
  return GITHUB_URL.test(url.trim());
}

function extractRepoName(url: string): string {
  return GITHUB_URL.exec(url.trim())?.[2] || 'unknown-repo';
}

export function useGitHubImport() {
  const { selectRepository } = useRepository();
  const addRepository = useAppStore((state) => state.addRepository);
  const [githubUrl, setGithubUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
  }, [addRepository, githubUrl, selectRepository]);

  return {
    githubUrl,
    setGithubUrl: setUrl,
    loading,
    error,
    empty: githubUrl.trim().length === 0,
    success: isValidGithubUrl(githubUrl),
    source: 'github' as const,
    previewName: isValidGithubUrl(githubUrl) ? extractRepoName(githubUrl) : null,
    analyseGithub,
    retry: clearError,
    refresh: clearError,
  };
}
