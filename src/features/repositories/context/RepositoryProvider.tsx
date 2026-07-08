import { useEffect, useMemo } from 'react';
import { backendService } from '@/services/backend';
import { useAppStore } from '@/store/useAppStore';
import { RepositoryContext, type RepositoryContextValue } from './repository-context';

export function RepositoryProvider({ children }: { children: React.ReactNode }) {
  const repositories = useAppStore((state) => state.repositories);
  const activeRepositoryId = useAppStore((state) => state.activeRepositoryId);
  const setActiveRepositoryId = useAppStore((state) => state.setActiveRepositoryId);
  const setRepositories = useAppStore((state) => state.setRepositories);

  useEffect(() => {
    let cancelled = false;
    async function loadRepositories() {
      const nextRepositories = await backendService.fetchRepositories();
      if (!cancelled) setRepositories(nextRepositories);
    }
    void loadRepositories();
    return () => {
      cancelled = true;
    };
  }, [setRepositories]);

  const value = useMemo<RepositoryContextValue>(() => {
    const activeRepository = repositories.find((repo) => repo.id === activeRepositoryId) || null;
    return {
      repositories,
      activeRepository,
      activeRepositoryId,
      completedRepositories: repositories.filter((repo) => repo.status === 'completed'),
      hasRepositories: repositories.length > 0,
      setActiveRepositoryId,
    };
  }, [activeRepositoryId, repositories, setActiveRepositoryId]);

  return (
    <RepositoryContext.Provider value={value}>
      {children}
    </RepositoryContext.Provider>
  );
}
