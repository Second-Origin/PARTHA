import { useMemo } from 'react';
import { useRepository } from './useRepository';

export function useRepositoryDashboard() {
  const repositoryState = useRepository();

  const metrics = useMemo(() => {
    const repositories = repositoryState.repositories;
    return {
      totalRepositories: repositories.length,
      completedRepositories: repositories.filter((repo) => repo.status === 'completed').length,
      totalFiles: repositories.reduce((total, repo) => total + repo.fileCount, 0),
      totalSize: repositories.reduce((total, repo) => total + repo.size, 0),
    };
  }, [repositoryState.repositories]);

  return {
    ...repositoryState,
    metrics,
  };
}
