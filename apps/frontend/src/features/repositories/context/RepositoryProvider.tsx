import { useCallback, useEffect, useMemo, useState } from 'react';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useAppStore } from '@/app/store/useAppStore';
import { RepositoryContext, type RepositoryContextValue } from './repository-context';

export function RepositoryProvider({ children }: { children: React.ReactNode }) {
  const repositories = useAppStore((state) => state.repositories);
  const activeRepositoryId = useAppStore((state) => state.activeRepositoryId);
  const setActiveRepositoryId = useAppStore((state) => state.setActiveRepositoryId);
  const setRepositories = useAppStore((state) => state.setRepositories);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRepositories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextRepositories = await backendService.fetchRepositories();
      setRepositories(nextRepositories);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [setRepositories]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const nextRepositories = await backendService.fetchRepositories();
        if (!cancelled) setRepositories(nextRepositories);
      } catch (caught) {
        if (!cancelled) setError(getErrorMessage(caught));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
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
      loading,
      error,
      setActiveRepositoryId,
      refresh: loadRepositories,
    };
  }, [activeRepositoryId, error, loadRepositories, loading, repositories, setActiveRepositoryId]);

  return (
    <RepositoryContext.Provider value={value}>
      {children}
    </RepositoryContext.Provider>
  );
}
