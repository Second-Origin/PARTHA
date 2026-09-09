import { useCallback, useEffect, useMemo, useState } from 'react';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useAppStore } from '@/app/store/useAppStore';
import { useAuthStore } from '@/app/store/useAuthStore';
import { RepositoryContext, type RepositoryContextValue } from './repository-context';

export function RepositoryProvider({ children }: { children: React.ReactNode }) {
  const repositories = useAppStore((state) => state.repositories);
  const activeRepositoryId = useAppStore((state) => state.activeRepositoryId);
  const setActiveRepositoryId = useAppStore((state) => state.setActiveRepositoryId);
  const setRepositories = useAppStore((state) => state.setRepositories);
  // Mounting only happens once RequireAuth confirms an authenticated session
  // (this provider lives inside MainLayout), which covers the common case.
  // This dependency additionally covers the case where the identity changes
  // *without* an intervening unmount, so a second user can never be served
  // straight from the first user's already-fetched state.
  const userId = useAuthStore((state) => state.user?.id);
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
  }, [setRepositories, userId]);

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
